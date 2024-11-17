from flask import Flask, request, jsonify
import pandas as pd
from datetime import datetime
import threading
import streamlit as st
import time

app = Flask(__name__)

# Хранилище данных
issues_data = []
update_needed = threading.Event()

@app.route('/webhook', methods=['POST'])
def webhook():
    global update_needed
    if request.method == 'POST':
        payload = request.json
        if payload:  # Проверяем, что данные пришли
            issues_data.append(payload)
            update_needed.set()  # Уведомляем, что данные обновились
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "failed"}), 400
