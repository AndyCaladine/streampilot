# =============================================================
# email.py — Resend email helper
# All outbound emails go through this module.
# =============================================================

import resend
from flask import current_app


LOGO_URL      = "https://stream-pilot.co.uk/static/images/logo-dark.PNG"
SITE_URL      = "https://stream-pilot.co.uk"
ACCENT_COLOUR = "#a855f7"


def _base_template(content: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background:#0a0a0a;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#0a0a0a;padding:40px 20px;">
        <tr>
          <td align="center">
            <table width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;">

              <!-- Logo header -->
              <tr>
                <td align="center" style="padding:0 0 24px 0;">
                  <a href="{SITE_URL}" style="text-decoration:none;">
                    <img src="{LOGO_URL}" alt="StreamPilot" width="220" style="display:block;border:0;">
                  </a>
                </td>
              </tr>

              <!-- Card -->
              <tr>
                <td style="background:#161616;border-radius:12px;border:1px solid #262626;padding:40px;">
                  {content}
                </td>
              </tr>

              <!-- Footer -->
              <tr>
                <td align="center" style="padding:24px 0 0 0;">
                  <p style="margin:0;font-size:12px;color:#525252;letter-spacing:1px;">
                    STREAMPILOT &bull; <a href="{SITE_URL}" style="color:#525252;text-decoration:none;">stream-pilot.co.uk</a>
                  </p>
                </td>
              </tr>

            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """


def send_email(to: str, subject: str, html: str) -> bool:
    try:
        resend.api_key = current_app.config["RESEND_API_KEY"]
        resend.Emails.send({
            "from":    current_app.config["RESEND_FROM_EMAIL"],
            "to":      to,
            "subject": subject,
            "html":    html,
        })
        return True
    except Exception as e:
        current_app.logger.error(f"[Email] Failed to send to {to}: {e}")
        return False


def send_password_changed_email(to: str, display_name: str) -> bool:
    content = f"""
      <h1 style="margin:0 0 8px 0;font-size:24px;font-weight:700;color:#ffffff;">
        Password changed
      </h1>
      <p style="margin:0 0 24px 0;font-size:15px;color:#a3a3a3;">
        Hi {display_name},
      </p>
      <p style="margin:0 0 16px 0;font-size:15px;color:#a3a3a3;line-height:1.6;">
        Your StreamPilot password was successfully changed.
      </p>
      <p style="margin:0 0 16px 0;font-size:15px;color:#a3a3a3;line-height:1.6;">
        If you made this change, no action is needed.
      </p>
      <div style="background:#1a1a1a;border-left:3px solid {ACCENT_COLOUR};border-radius:0 6px 6px 0;padding:16px 20px;margin:24px 0;">
        <p style="margin:0;font-size:14px;color:#a3a3a3;line-height:1.6;">
          If this wasn't you, please contact us immediately via
          <strong style="color:#ffffff;">Settings → Contact Us</strong> in your dashboard.
        </p>
      </div>
      <hr style="border:none;border-top:1px solid #262626;margin:32px 0 0 0;">
    """
    return send_email(to, "Your StreamPilot password has been changed", _base_template(content))


def send_password_reset_email(to: str, display_name: str, reset_url: str, expires_at) -> bool:
    content = f"""
      <h1 style="margin:0 0 8px 0;font-size:24px;font-weight:700;color:#ffffff;">
        Reset your password
      </h1>
      <p style="margin:0 0 24px 0;font-size:15px;color:#a3a3a3;">
        Hi {display_name},
      </p>
      <p style="margin:0 0 24px 0;font-size:15px;color:#a3a3a3;line-height:1.6;">
        We received a request to reset your StreamPilot password.
        Click the button below to choose a new one.
      </p>

      <!-- CTA Button -->
      <table cellpadding="0" cellspacing="0" style="margin:0 0 24px 0;">
        <tr>
          <td style="border-radius:8px;background:{ACCENT_COLOUR};">
            <a href="{reset_url}"
               style="display:inline-block;padding:14px 28px;font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:8px;letter-spacing:0.5px;">
              Reset my password
            </a>
          </td>
        </tr>
      </table>

    <p style="margin:0 0 16px 0;font-size:14px;color:#737373;line-height:1.6;">
        This link expires at <strong style="color:#a3a3a3;">{expires_at.strftime("%H:%M UTC")}</strong> 
        — valid for 1 hour from when this email was sent.
    </p>
      <p style="margin:0 0 0 0;font-size:14px;color:#737373;line-height:1.6;">
        If you didn't request this, you can safely ignore this email — your password won't change.
      </p>
      <hr style="border:none;border-top:1px solid #262626;margin:32px 0 0 0;">
    """
    return send_email(to, "Reset your StreamPilot password", _base_template(content))