import sys
sys.stdout.reconfigure(encoding='utf-8')

from jira import JIRA
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from datetime import datetime
import time
import gc

st.title("Sprint Health Dashboard with Advanced Metrics")
default_api_token = 'ATATT3'
default_api_token += 'xFfGF0MDTSE9LgxG7tCEVBlRXMlEgZgcmQSwzT7UfBeAsXiyqw5Gxwaa8AI70_unSH8zZWnv2ux653kE_F7N6oCQLOfc6nW1mi5fqfKqv5AXS1'
default_api_token += 've898P8YVx9AV4g-GX1UlFADexbzoolACtsyOeCqO9lykrQJwjlf8mEDUaN4B9ZxgOs=314EC44E'

jira_base_url = st.text_input("Введите URL вашего Jira пространства(ДЛЯ ЗАПУСКА ДЕМО ОСТАВЬТЕ ЗНАЧЕНИЯ ПО УМОЛЧАНИЮ):", "https://funnysemen.atlassian.net")
api_token = st.text_input("Введите ваш API Token(ДЛЯ ЗАПУСКА ДЕМО ОСТАВЬТЕ ЗНАЧЕНИЯ ПО УМОЛЧАНИЮ):", 
                          default_api_token, 
                          type="password")
email = st.text_input("Введите ваш Email для авторизации(ДЛЯ ЗАПУСКА ДЕМО ОСТАВЬТЕ ЗНАЧЕНИЯ ПО УМОЛЧАНИЮ):", "funnysemen@gmail.com")
project_key = st.text_input("Введите ключ проекта (например, SCRUM)(ДЛЯ ЗАПУСКА ДЕМО ОСТАВЬТЕ ЗНАЧЕНИЯ ПО УМОЛЧАНИЮ):", "SCRUM")
update_interval = 5

if not jira_base_url or not api_token or not email or not project_key:
    st.warning("Пожалуйста, заполните все поля для начала работы.")
    st.stop()

jira_options = {'server': jira_base_url}
jira = JIRA(options=jira_options, basic_auth=(email, api_token))

weights = {
    "Engagement": 1.5,
    "Task Quality": 1,
    "Board Quality": 0.5,
    "Health Score": 1,  # Итоговый скор
}

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

def calculate_metrics(df, sprint_duration_weeks):
    total_tasks = len(df)

    engagement_submetrics = {
        "Assigned Tasks (%)": len(df[df["Assignee"] != "Unassigned"]) / total_tasks * 100 if total_tasks > 0 else 0,
        "Balanced Task Distribution (%)": 100 - (df["Assignee"].value_counts().std() / total_tasks * 100) if total_tasks > 1 else 100,
        "Tasks with Comments (%)": len([task for task in df["Summary"] if "comment" in task.lower()]) / total_tasks * 100 if total_tasks > 0 else 0,
        "Tasks with Subtasks (%)": len(df[df["Subtasks"] > 0]) / total_tasks * 100 if total_tasks > 0 else 0,
    }
    engagement = sum(engagement_submetrics.values()) / len(engagement_submetrics) if engagement_submetrics else 0

    task_quality_submetrics = {
        "Tasks with Descriptions (%)": len(df[df["Description"] == 1]) / total_tasks * 100 if total_tasks > 0 else 0,
        "Tasks with Subtasks (%)": len(df[df["Subtasks"] > 0]) / total_tasks * 100 if total_tasks > 0 else 0,
        "Tasks with Story Points (%)": len(df[df["Story Points"].notna()]) / total_tasks * 100 if total_tasks > 0 else 0,
    }
    task_quality = sum(task_quality_submetrics.values()) / len(task_quality_submetrics) if task_quality_submetrics else 0

    board_quality_submetrics = {
        "Backlog Managed (%)": len(df[df["Status"].str.lower() != "backlog"]) / total_tasks * 100 if total_tasks > 0 else 100,
        "Git Integration Configured (%)": 100 if "git" in df["Summary"].str.lower().values else 0,
        "Active Sprint Workflow Rules (%)": 100 if "workflow" in df["Summary"].str.lower().values else 0,
    }
    board_quality = sum(board_quality_submetrics.values()) / len(board_quality_submetrics) if board_quality_submetrics else 0

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

def get_color(value):
    if value <= 20:
        return "#FF0000"
    elif 21 <= value <= 35:
        return "#FFA500"
    else:
        return "#4CAF50"

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

if st.button("Запустить анализ"):
    metrics_container = st.empty()
    backlog_container = st.empty()
    while True:
        try:
            df = fetch_data(project_key)
            metrics = calculate_metrics(df, 2)
            render_circular_metrics(metrics, metrics_container)
            
            with backlog_container:
                st.subheader("Backlog Overview")
                st.dataframe(df[["Key", "Summary", "Status", "Assignee", "Story Points", "Sprint"]])
            
        except Exception as e:
            st.error(f"Ошибка: {e}")
        time.sleep(update_interval)
        gc.collect()
