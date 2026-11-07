"""SMTP отправка и IMAP приём писем."""

import email
import imaplib
import json
import re
import smtplib
import uuid
from datetime import datetime, timezone
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import parseaddr, parsedate_to_datetime
from typing import Optional

from sqlalchemy.orm import Session

from . import models
from .timeline import add_event, add_client_event


def get_settings(db: Session) -> Optional[models.EmailSettings]:
    return db.query(models.EmailSettings).filter(models.EmailSettings.id == 1).first()


def get_or_create_settings(db: Session) -> models.EmailSettings:
    settings = get_settings(db)
    if settings is None:
        settings = models.EmailSettings(id=1)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def is_configured(settings: models.EmailSettings) -> bool:
    return bool(settings.smtp_host and settings.from_email)


def is_imap_configured(settings: models.EmailSettings) -> bool:
    return bool(settings.imap_host and (settings.imap_user or settings.from_email))


def _new_message_id(from_email: str) -> str:
    domain = "simple-crm.local"
    if from_email and "@" in from_email:
        domain = from_email.split("@", 1)[1]
    return f"<{uuid.uuid4().hex}@{domain}>"


def send_email(
    settings: models.EmailSettings,
    *,
    to_emails: list[str],
    subject: str,
    body: str,
    cc_emails: Optional[list[str]] = None,
    in_reply_to: Optional[str] = None,
) -> str:
    """Отправить письмо. Возвращает Message-ID."""
    if not is_configured(settings):
        raise RuntimeError("Почтовая интеграция не настроена")
    if not to_emails:
        raise RuntimeError("Укажите хотя бы одного получателя")

    msg = EmailMessage()
    from_name = settings.from_name or "Simple CRM"
    msg["From"] = f"{from_name} <{settings.from_email}>"
    msg["To"] = ", ".join(to_emails)
    if cc_emails:
        msg["Cc"] = ", ".join(cc_emails)
    msg["Subject"] = subject
    message_id = _new_message_id(settings.from_email)
    msg["Message-ID"] = message_id
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to
    msg.set_content(body)

    recipients = list(to_emails) + list(cc_emails or [])

    if settings.use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password or "")
            smtp.send_message(msg, to_addrs=recipients)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.ehlo()
            if settings.use_tls:
                smtp.starttls()
                smtp.ehlo()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password or "")
            smtp.send_message(msg, to_addrs=recipients)
    return message_id


def _decode_mime(value: Optional[str]) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        plain = None
        html = None
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp:
                continue
            try:
                payload = part.get_payload(decode=True) or b""
                charset = part.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")
            except Exception:
                continue
            if ctype == "text/plain" and plain is None:
                plain = text
            elif ctype == "text/html" and html is None:
                html = text
        if plain:
            return plain.strip()
        if html:
            return re.sub(r"<[^>]+>", " ", html).strip()
        return ""
    try:
        payload = msg.get_payload(decode=True) or b""
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace").strip()
    except Exception:
        return str(msg.get_payload() or "")


def _normalize_msgid(value: Optional[str]) -> str:
    if not value:
        return ""
    return value.strip()


def _find_client_by_email(db: Session, addr: str) -> Optional[models.Client]:
    if not addr:
        return None
    needle = addr.strip().lower()
    clients = db.query(models.Client).filter(models.Client.email != "").all()
    for c in clients:
        if (c.email or "").strip().lower() == needle:
            return c
    return None


def _parent_outbound(db: Session, in_reply_to: str) -> Optional[models.MailMessage]:
    if not in_reply_to:
        return None
    return (
        db.query(models.MailMessage)
        .filter(
            models.MailMessage.message_id == in_reply_to,
            models.MailMessage.direction == models.MailDirection.OUTBOUND,
        )
        .first()
    )


def store_outbound(
    db: Session,
    *,
    task: models.Task,
    actor_id: int,
    to_emails: list[str],
    cc_emails: list[str],
    subject: str,
    body: str,
    message_id: str,
) -> models.MailMessage:
    mail = models.MailMessage(
        client_id=task.client_id,
        task_id=task.id,
        direction=models.MailDirection.OUTBOUND,
        subject=subject,
        body=body,
        from_addr="",
        to_addrs=json.dumps(to_emails, ensure_ascii=False),
        cc_addrs=json.dumps(cc_emails or [], ensure_ascii=False),
        message_id=_normalize_msgid(message_id),
        in_reply_to="",
        actor_id=actor_id,
    )
    settings = get_settings(db)
    if settings and settings.from_email:
        mail.from_addr = settings.from_email
    db.add(mail)
    db.flush()

    recipients = ", ".join(to_emails)
    add_event(
        db,
        task.id,
        models.TimelineEventType.EMAIL_SENT,
        f"Письмо: {subject}",
        actor_id=actor_id,
        detail=f"Кому: {recipients}\n\n{body[:500]}",
        meta={
            "to": to_emails,
            "cc": cc_emails,
            "subject": subject,
            "mail_id": mail.id,
            "message_id": mail.message_id,
        },
        mirror_to_client=False,
    )
    if task.client_id:
        add_client_event(
            db,
            task.client_id,
            models.ClientEventType.EMAIL_SENT,
            f"Письмо: {subject}",
            actor_id=actor_id,
            detail=f"Задача #{task.id} · Кому: {recipients}\n\n{body[:500]}",
            meta={
                "task_id": task.id,
                "mail_id": mail.id,
                "message_id": mail.message_id,
                "to": to_emails,
            },
        )
    return mail


def _store_inbound(
    db: Session,
    *,
    from_addr: str,
    to_addrs: list[str],
    subject: str,
    body: str,
    message_id: str,
    in_reply_to: str,
    imap_uid: str,
    created_at,
) -> Optional[models.MailMessage]:
    if message_id:
        exists = (
            db.query(models.MailMessage)
            .filter(models.MailMessage.message_id == message_id)
            .first()
        )
        if exists:
            return None
    if imap_uid:
        exists = (
            db.query(models.MailMessage)
            .filter(models.MailMessage.imap_uid == imap_uid)
            .first()
        )
        if exists:
            return None

    parent = _parent_outbound(db, in_reply_to)
    client = None
    task_id = None
    if parent:
        client = parent.client
        task_id = parent.task_id
        if client is None and parent.client_id:
            client = db.query(models.Client).filter(models.Client.id == parent.client_id).first()
    if client is None:
        client = _find_client_by_email(db, from_addr)
    if client is None and not task_id:
        # неизвестный отправитель — пропускаем
        return None

    mail = models.MailMessage(
        client_id=client.id if client else None,
        task_id=task_id,
        direction=models.MailDirection.INBOUND,
        subject=subject,
        body=body,
        from_addr=from_addr,
        to_addrs=json.dumps(to_addrs, ensure_ascii=False),
        cc_addrs="[]",
        message_id=message_id,
        in_reply_to=in_reply_to,
        imap_uid=imap_uid,
        created_at=created_at,
    )
    db.add(mail)
    db.flush()

    title = f"Ответ: {subject}" if subject else "Входящее письмо"
    preview = strip_quoted_reply(body)[:500]
    detail = f"От: {from_addr}\n\n{preview}"
    meta = {
        "mail_id": mail.id,
        "message_id": message_id,
        "from": from_addr,
        "task_id": task_id,
    }
    if task_id:
        add_event(
            db,
            task_id,
            models.TimelineEventType.EMAIL_RECEIVED,
            title,
            detail=detail,
            meta=meta,
            mirror_to_client=False,
        )
    if client:
        add_client_event(
            db,
            client.id,
            models.ClientEventType.EMAIL_RECEIVED,
            title,
            detail=detail if not task_id else f"Задача #{task_id} · {detail}",
            meta=meta,
        )

    # автоматизация: «новое письмо от клиента»
    try:
        from .automation import run_client_email_rules

        linked_task = None
        if task_id:
            linked_task = (
                db.query(models.Task).filter(models.Task.id == task_id).first()
            )
        if client is not None:
            run_client_email_rules(
                db,
                client=client,
                source_mail=mail,
                source_task=linked_task,
            )
    except Exception:
        pass

    return mail


def fetch_inbound_emails(db: Session) -> list[models.MailMessage]:
    """Забрать новые письма по IMAP. Возвращает список сохранённых."""
    settings = get_settings(db)
    if settings is None or not is_imap_configured(settings):
        return []

    user = settings.imap_user or settings.smtp_user or settings.from_email
    password = settings.imap_password or settings.smtp_password or ""
    folder = settings.imap_folder or "INBOX"
    last_uid = int(settings.imap_last_uid or 0)
    saved: list[models.MailMessage] = []

    try:
        if settings.imap_use_ssl:
            imap = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port or 993)
        else:
            imap = imaplib.IMAP4(settings.imap_host, settings.imap_port or 143)
        imap.login(user, password)
        imap.select(folder, readonly=True)

        criteria = f"{last_uid + 1}:*" if last_uid > 0 else "1:*"
        status, data = imap.uid("search", None, criteria)
        if status != "OK":
            imap.logout()
            return []

        uids = [u for u in (data[0] or b"").split() if u]
        max_uid = last_uid
        for uid_b in uids[-100:]:  # ограничим пачку
            uid = int(uid_b.decode() if isinstance(uid_b, bytes) else uid_b)
            if uid <= last_uid:
                continue
            max_uid = max(max_uid, uid)
            st, msg_data = imap.uid("fetch", str(uid), "(RFC822)")
            if st != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            from_addr = parseaddr(msg.get("From", ""))[1]
            to_raw = msg.get("To", "") or ""
            to_addrs = [
                parseaddr(p)[1]
                for p in to_raw.split(",")
                if parseaddr(p)[1]
            ]
            subject = _decode_mime(msg.get("Subject"))
            body = _extract_body(msg)
            message_id = _normalize_msgid(msg.get("Message-ID"))
            in_reply_to = _normalize_msgid(msg.get("In-Reply-To"))
            try:
                created_at = parsedate_to_datetime(msg.get("Date"))
                if created_at is not None:
                    # Date из письма — в локали отправителя; в БД храним UTC (naive)
                    if created_at.tzinfo is not None:
                        created_at = created_at.astimezone(timezone.utc).replace(
                            tzinfo=None
                        )
                    # без tzinfo считаем уже UTC (редко)
            except Exception:
                created_at = None
            if created_at is None:
                created_at = datetime.utcnow()

            stored = _store_inbound(
                db,
                from_addr=from_addr,
                to_addrs=to_addrs,
                subject=subject,
                body=body,
                message_id=message_id,
                in_reply_to=in_reply_to,
                imap_uid=str(uid),
                created_at=created_at,
            )
            if stored:
                saved.append(stored)

        settings.imap_last_uid = max_uid
        db.commit()
        imap.logout()
    except Exception:
        db.rollback()
        return saved
    return saved


def strip_quoted_reply(body: str) -> str:
    """Оставить только новый текст без цитаты ответа и подписи."""
    if not body:
        return ""
    lines = body.replace("\r\n", "\n").split("\n")
    cut = len(lines)
    reply_header = re.compile(
        r"^(On\s.+wrote:|Am\s.+schrieb\s|Le\s.+a écrit|El\s.+escribió)",
        re.IGNORECASE,
    )
    ru_header = re.compile(r"\d{1,2}[:.]\d{2}.+\sот\s+.+:\s*$", re.IGNORECASE)
    for i, line in enumerate(lines):
        trimmed = line.strip()
        if trimmed in ("--", "-- "):
            cut = i
            break
        if line.lstrip().startswith(">"):
            cut = i
            while cut > 0 and not lines[cut - 1].strip():
                cut -= 1
            break
        if (
            reply_header.match(trimmed)
            or ru_header.search(trimmed)
            or re.match(r"^From:\s*.+", trimmed, re.IGNORECASE)
            or (i > 0 and re.match(r"^От:\s*.+", trimmed, re.IGNORECASE))
        ):
            cut = i
            while cut > 0 and not lines[cut - 1].strip():
                cut -= 1
            break
    main = lines[:cut]
    while main:
        last = main[-1].strip()
        if (
            not last
            or re.match(r"^Отправлено из Почты", last, re.IGNORECASE)
            or re.match(r"^Sent from my ", last, re.IGNORECASE)
            or re.match(r"^Get Outlook for ", last, re.IGNORECASE)
        ):
            main.pop()
            continue
        break
    text = "\n".join(main).strip()
    return text or body.strip()


def mail_to_dict(m: models.MailMessage) -> dict:
    def _list(raw: str) -> list[str]:
        try:
            data = json.loads(raw or "[]")
            return [str(x) for x in data]
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    return {
        "id": m.id,
        "client_id": m.client_id,
        "task_id": m.task_id,
        "direction": m.direction.value if hasattr(m.direction, "value") else m.direction,
        "subject": m.subject or "",
        "body": m.body or "",
        "from_addr": m.from_addr or "",
        "to_addrs": _list(m.to_addrs),
        "cc_addrs": _list(m.cc_addrs),
        "message_id": m.message_id or "",
        "in_reply_to": m.in_reply_to or "",
        "actor_id": m.actor_id,
        "created_at": m.created_at,
        "actor": m.actor,
    }
