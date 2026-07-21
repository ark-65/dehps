"""Outbound notification transports for operator-controlled DEHPS messages."""

from dehps.notifications.mail import (
    MailConfigurationError,
    MailDeliveryError,
    MailDeliveryReceipt,
    QqMailConfig,
    QqMailService,
)
from dehps.notifications.mainline_prediction import (
    MainlinePredictionEmail,
    MainlinePredictionMailError,
    MainlinePredictionNotificationService,
    PredictionDeliveryStateError,
    PredictionMailDeliveryLedger,
    compile_mainline_prediction_email,
    require_pre_draw_delivery_window,
)

__all__ = [
    "MailConfigurationError",
    "MailDeliveryError",
    "MailDeliveryReceipt",
    "QqMailConfig",
    "QqMailService",
    "MainlinePredictionEmail",
    "MainlinePredictionMailError",
    "MainlinePredictionNotificationService",
    "PredictionDeliveryStateError",
    "PredictionMailDeliveryLedger",
    "compile_mainline_prediction_email",
    "require_pre_draw_delivery_window",
]
