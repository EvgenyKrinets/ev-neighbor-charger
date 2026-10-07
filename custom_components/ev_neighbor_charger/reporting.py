"""Localized mail reports; network work runs in the executor."""
from datetime import datetime
from email.message import EmailMessage
import csv
import io
import re
import smtplib
import ssl

LABELS = {
 "en": ["Charging started", "Charging finished", "Monthly charging report", "Start", "End", "Duration (minutes)", "Energy (kWh)", "Cost (ILS)", "Rate (ILS/kWh)", "Reason", "Total"],
 "ru": ["Зарядка началась", "Зарядка завершена", "Ежемесячный отчёт о зарядках", "Начало", "Окончание", "Длительность (мин)", "Энергия (кВт·ч)", "Стоимость (₪)", "Тариф (₪/кВт·ч)", "Причина", "Итого"],
 "he": ["הטעינה התחילה", "הטעינה הסתיימה", "דוח טעינה חודשי", "התחלה", "סיום", "משך (דקות)", "אנרגיה (קוט״ש)", "עלות (₪)", "תעריף (₪ לקוט״ש)", "סיבה", "סך הכול"],
}
REASONS = {"en": {"idle_timeout": "Low power automatic shutoff", "switch_off": "Switch turned off", "completed": "Completed"}, "ru": {"idle_timeout": "Автоотключение: низкая мощность", "switch_off": "Выключатель отключён", "completed": "Завершено"}, "he": {"idle_timeout": "כיבוי אוטומטי עקב הספק נמוך", "switch_off": "המתג כובה", "completed": "הושלם"}}

def valid_email(value):
    return isinstance(value, str) and len(value) <= 254 and bool(re.fullmatch(r"[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+", value))

def session_row(record, tz, language="en"):
    start = datetime.fromisoformat(record["start"]).astimezone(tz)
    end = datetime.fromisoformat(record["end"]).astimezone(tz) if record.get("end") else None
    return [start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds") if end else "—", round((end-start).total_seconds()/60, 1) if end else "—", record.get("energy_kwh", "—"), record.get("cost", "—"), record.get("rate", 0), REASONS[language].get(record.get("reason"), record.get("reason", "—"))]

def make_message(job, sender, tz):
    language = job.get("language", "en")
    if language not in LABELS:
        language = "en"
    labels = LABELS[language]
    if job["kind"] == "test":
        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = job["email"]
        msg["Subject"] = {"ru": "Проверка почты EV Neighbor Charger", "en": "EV Neighbor Charger email test", "he": "בדיקת דוא״ל EV Neighbor Charger"}[language]
        msg.set_content({"ru": "Это тестовое письмо из настроек интеграции EV Neighbor Charger. SMTP-сервер принял отправку.", "en": "This is a test email from EV Neighbor Charger integration settings. The SMTP server accepted the message.", "he": "זוהי הודעת בדיקה מהגדרות EV Neighbor Charger. שרת SMTP קיבל את ההודעה."}[language])
        return msg
    records = job["records"]
    subject = labels[{"start": 0, "end": 1, "monthly": 2}[job["kind"]]]
    if job.get("month"):
        subject += " · " + job["month"]
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = job["email"]
    msg["Subject"] = subject
    rows = [session_row(r, tz, language) for r in records]
    total = f"{labels[10]}: {sum(r.get('energy_kwh', 0) for r in records):.3f} kWh · {sum(r.get('cost', 0) for r in records):.2f} ILS"
    body = subject + "\n" + (job.get("name") or "") + "\n\n"
    body += "\n\n".join("\n".join(f"{label}: {value}" for label, value in zip(labels[3:10], row)) for row in rows)
    if job["kind"] != "start":
        body += "\n\n" + total
    msg.set_content(body)
    if job["kind"] == "monthly":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(labels[3:10])
        writer.writerows(rows)
        writer.writerow([labels[10], "", "", sum(r.get("energy_kwh", 0) for r in records), sum(r.get("cost", 0) for r in records)])
        msg.add_attachment(output.getvalue().encode("utf-8-sig"), maintype="text", subtype="csv", filename=f"charging-{job['month']}.csv")
    return msg

def send_mail(settings, job, tz):
    message = make_message(job, settings["smtp_sender"], tz)
    security = settings.get("smtp_security", "starttls")
    context = ssl.create_default_context()
    factory = smtplib.SMTP_SSL if security == "ssl" else smtplib.SMTP
    kwargs = {"timeout": 20}
    if security == "ssl":
        kwargs["context"] = context
    with factory(settings["smtp_host"], int(settings.get("smtp_port", 587)), **kwargs) as client:
        if security == "starttls":
            client.starttls(context=context)
        if settings.get("smtp_username"):
            client.login(settings["smtp_username"], settings.get("smtp_password", ""))
        client.send_message(message)


def smtp_error_detail(error, settings):
    """Describe SMTP failures without showing login secrets or header controls."""
    detail = str(error)
    for key in ("smtp_password", "smtp_username"):
        secret = settings.get(key)
        if secret:
            detail = detail.replace(secret, "[redacted]")
    return " ".join(detail.split())[:600] or type(error).__name__
