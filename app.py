import sys
sys.stdout.reconfigure(encoding='utf-8')

from jira import JIRA
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from datetime import datetime
import time
import gc

# --- Streamlit интерфейс ---
st.title("Sprint Health Dashboard with Advanced Metrics")

# Ввод данных пользователя
jira_base_url = st.text_input("Введите URL вашего Jira пространства:", "https://funnysemen.atlassian.net")
api_token = st.text_input("Введите ваш API Token:", 
                          "ATATT3xFfGF0J92FBvKYXEjQrhJqg5JnB7hp_FzbGqU18x_ZpOk5nT8BCk63q8g_dPUMAytoj_E6a45gZZn03ItMwBl4WFXWM-lcCNPzStWpOfT8WL4uc6JL2m2RCJa3BEHRpbiJMqiIvU0kSbgExyrN4yGCMaoXVcugylg5IQU-tOjCcO_cCsA=C632C318", 
                          type="password")
email = st.text_input("Введите ваш Email для авторизации:", "funnysemen@gmail.com")
project_key = st.text_input("Введите ключ проекта (например, SCRUM):", "SCRUM")
update_interval = 5

# Проверяем, введены ли все данные
if not jira_base_url or not api_token or not email or not project_key:
    st.warning("Пожалуйста, заполните все поля для начала работы.")
    st.stop()

# --- Конфигурация Jira ---
jira_options = {'server': jira_base_url}
jira = JIRA(options=jira_options, basic_auth=(email, api_token))

# Весовые коэффициенты метрик
weights = {
    "Engagement": 1.5,
    "Task Quality": 1,
    "Board Quality": 0.5,
    "Health Score": 1,  # Итоговый скор
}

# --- Функция для получения данных из Jira ---
def fetch_data(project_key):
    jql = f'project = {project_key}'
    issues = jira.search_issues(jql, maxResults=100)
    data = []

    for issue in issues:
        fields = issue.fields
        summary = fields.summary.encode('utf-8').decode('utf-8') if fields.summary else "No Summary"
        status = fields.status.name.encode('utf-8').decode('utf-8') if fields.status else "No Status"
        created_date = datetime.strptime(fields.created.split(".")[0], '%Y-%m-%dT%H:%M:%S')
        updated_date = datetime.strptime(fields.updated.split(".")[0], '%Y-%m-%dT%H:%M:%S')
        story_points = getattr(fields, 'customfield_10016', None)
        subtasks = len(fields.subtasks) if hasattr(fields, 'subtasks') else 0

        data.append({
            "Key": issue.key,
            "Summary": summary,
            "Status": status,
            "Assignee": fields.assignee.displayName if fields.assignee else "Unassigned",
            "Created": fields.created,
            "Updated": fields.updated,
            "Duration (days)": (updated_date - created_date).days,
            "Story Points": story_points,
            "Subtasks": subtasks,
            "Description": 1 if bool(fields.description) else 0,
            "Sprint": fields.customfield_10020[0].name if fields.customfield_10020 and isinstance(fields.customfield_10020, list) else None,
        })

    return pd.DataFrame(data)

# --- Подсчёт метрик ---
def calculate_metrics(df, sprint_duration_weeks):
    total_tasks = len(df)

    # --- Engagement ---
    engagement_submetrics = {
        "Assigned Tasks (%)": len(df[df["Assignee"] != "Unassigned"]) / total_tasks * 100 if total_tasks > 0 else 0,
        "Balanced Task Distribution (%)": 100 - (df["Assignee"].value_counts().std() / total_tasks * 100) if total_tasks > 1 else 100,
        "Tasks with Comments (%)": len([task for task in df["Summary"] if "comment" in task.lower()]) / total_tasks * 100 if total_tasks > 0 else 0,
        "Tasks with Subtasks (%)": len(df[df["Subtasks"] > 0]) / total_tasks * 100 if total_tasks > 0 else 0,
    }
    engagement = sum(engagement_submetrics.values()) / len(engagement_submetrics) if engagement_submetrics else 0

    # --- Task Quality ---
    task_quality_submetrics = {
        "Tasks with Descriptions (%)": len(df[df["Description"] == 1]) / total_tasks * 100 if total_tasks > 0 else 0,
        "Tasks with Subtasks (%)": len(df[df["Subtasks"] > 0]) / total_tasks * 100 if total_tasks > 0 else 0,
        "Tasks with Story Points (%)": len(df[df["Story Points"].notna()]) / total_tasks * 100 if total_tasks > 0 else 0,
    }
    task_quality = sum(task_quality_submetrics.values()) / len(task_quality_submetrics) if task_quality_submetrics else 0

    # --- Board Quality ---
    board_quality_submetrics = {
        "Backlog Managed (%)": len(df[df["Status"].str.lower() != "backlog"]) / total_tasks * 100 if total_tasks > 0 else 100,
        "Git Integration Configured (%)": 100 if "git" in df["Summary"].str.lower().values else 0,
        "Active Sprint Workflow Rules (%)": 100 if "workflow" in df["Summary"].str.lower().values else 0,
    }
    board_quality = sum(board_quality_submetrics.values()) / len(board_quality_submetrics) if board_quality_submetrics else 0

    # --- Итоговый Health Score ---
    health_score = (
        weights["Engagement"] * engagement +
        weights["Task Quality"] * task_quality +
        weights["Board Quality"] * board_quality
    ) / sum(weights.values())

    return {
        "Engagement (%)": engagement,
        "Task Quality (%)": task_quality,
        "Board Quality (%)": board_quality,
        "Health Score (%)": health_score,
    }

# --- Функция для выбора цвета по значению ---
def get_color(value):
    if value <= 20:
        return "#FF0000"  # Красный
    elif 21 <= value <= 35:
        return "#FFA500"  # Желтый
    else:
        return "#4CAF50"  # Зеленый

# --- Визуализация метрик ---
def render_circular_metrics(metrics, container):
    with container:
        cols = st.columns(len(metrics))
        for col, (metric, value) in zip(cols, metrics.items()):
            if metric != "Details":
                with col:
                    color = get_color(value)
                    fig, ax = plt.subplots(figsize=(1.5, 1.5), facecolor="none")
                    ax.pie(
                        [value, 100 - value],
                        colors=[color, "#838383"],
                        startangle=90,
                        counterclock=False,
                        wedgeprops={"width": 0.05},
                    )
                    ax.text(
                        0, 0, f"{value:.0f}%",
                        ha="center", va="center",
                        fontsize=14, color="white", fontweight="bold"
                    )
                    ax.set(aspect="equal")
                    st.pyplot(fig)
                    plt.close(fig)
                    st.caption(metric)

# --- Основной цикл ---
if st.button("Запустить анализ"):
    metrics_container = st.empty()  # Контейнер для обновления метрик
    backlog_container = st.empty()  # Контейнер для отображения бэклога
    while True:
        try:
            df = fetch_data(project_key)
            metrics = calculate_metrics(df, 2)
            render_circular_metrics(metrics, metrics_container)  # Обновляем контейнер с метриками
            
            with backlog_container:
                st.subheader("Backlog Overview")
                st.dataframe(df[["Key", "Summary", "Status", "Assignee", "Story Points", "Sprint"]])
            
        except Exception as e:
            st.error(f"Ошибка: {e}")
        time.sleep(update_interval)
        gc.collect()
