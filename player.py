# -*- coding: utf-8 -*-
"""
PyQt dynamic multimedia compatibility layer.
"""

# QtMultimedia (prefer PyQt6, fallback to PyQt5).
try:
    from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer  # type: ignore
    HAS_MEDIA = True
    QT_MAJOR = 6
    QMediaContent = None
except Exception:
    try:
        from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer  # type: ignore
        HAS_MEDIA = True
        QT_MAJOR = 5
        QAudioOutput = None
    except Exception:
        HAS_MEDIA = False
        QT_MAJOR = 0
        QMediaPlayer = None
        QAudioOutput = None
        QMediaContent = None
