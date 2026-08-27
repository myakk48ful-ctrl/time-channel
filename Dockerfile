# ─────────────────────────────────────────────────────────────
#  Dockerfile برای استقرار ربات تلگرام روی Railway
#  (بدون پروکسی — دیتاسنتر Railway به تلگرام دسترسی مستقیم دارد)
# ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# نصب وابستگی‌ها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی سورس
COPY bot.py .

# اجرای ربات (فرایند طولانی‌مدت Worker)
CMD ["python", "-u", "bot.py"]
