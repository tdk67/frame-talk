"""
Script to generate the official Frame Talk System Architecture PDF
using ReportLab with vector styling, structured component matrices,
mathematical formulas, multi-agent collaboration diagrams, and hexagonal architecture.
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Group, Polygon
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.core.config import config

OUTPUT_PDF = "ARCHITECTURE.pdf"

def build_architecture_pdf():
    doc = SimpleDocTemplate(
        OUTPUT_PDF,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=32,
        bottomMargin=32
    )

    styles = getSampleStyleSheet()

    # Custom Color Palette
    PRIMARY = colors.HexColor("#0F172A")     # Slate 900
    SECONDARY = colors.HexColor("#1E293B")   # Slate 800
    ACCENT_BLUE = colors.HexColor("#2563EB") # Blue 600
    ACCENT_GREEN = colors.HexColor("#16A34A")# Green 600
    ACCENT_AMBER = colors.HexColor("#D97706")# Amber 600
    ACCENT_PURPLE = colors.HexColor("#7C3AED")# Purple 600
    BG_LIGHT = colors.HexColor("#F8FAFC")    # Slate 50
    BORDER_COLOR = colors.HexColor("#CBD5E1")# Slate 300
    TEXT_MUTED = colors.HexColor("#64748B")  # Slate 500

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=PRIMARY
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=TEXT_MUTED
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=PRIMARY,
        spaceBefore=8,
        spaceAfter=4
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=ACCENT_BLUE,
        spaceBefore=6,
        spaceAfter=3
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=SECONDARY
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=10.5,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=SECONDARY
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=PRIMARY
    )

    story = []

    # =========================================================================
    # PAGE 1: HEADER + EXECUTIVE SUMMARY + MULTI-AGENT COLLABORATION DIAGRAM
    # =========================================================================
    story.append(Paragraph("🎙️ Frame Talk: System Architecture & Engineering Specification", title_style))
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        f"<b>Built for the Agentic Cinema Hackathon</b> | Live Studio: <b>{config.app_url}</b> | "
        f"Observability: <b>{config.grafana_url}</b>", subtitle_style
    ))
    story.append(Spacer(1, 5))
    story.append(HRFlowable(width="100%", thickness=1.5, color=ACCENT_BLUE, spaceAfter=6))

    story.append(Paragraph("1. Executive Summary & The Chronos Breakthrough", h1_style))
    story.append(Paragraph(
        "<b>Frame Talk</b> transforms silent developer screencasts (<code>.mp4</code>) and technical documentation "
        "(<code>README.md</code>) into synchronized, two-host technical podcast walkthroughs. "
        "Unlike text-only audio generators (NotebookLM) which cannot visually inspect UI actions, and fixed-speed video players "
        "that suffer from audio-visual drift, Frame Talk introduces the <b>Chronos Dynamic Visual Hold</b>. By metering speech down to the millisecond "
        "from 24 kHz raw PCM, Chronos dynamically stretches the video timeline at the focal action point, holding UI states so visuals and "
        "complex technical explanations conclude in exact lockstep without robotic silence buffers.",
        body_style
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("2. Multi-Agent Collaboration Workflow & Adversarial Feedback Loop", h1_style))
    story.append(Paragraph(
        "The system executes an autonomous choreography of specialized agents with a continuous adversarial quality feedback loop:",
        body_style
    ))
    story.append(Spacer(1, 4))

    # --- Multi-Agent Vector Diagram ---
    d_agents = Drawing(540, 160)
    # Background Canvas
    d_agents.add(Rect(0, 0, 540, 160, fillColor=BG_LIGHT, strokeColor=BORDER_COLOR, strokeWidth=1, rx=6, ry=6))

    agent_boxes = [
        ("1. Ingestion Agent", "gemini-3.7-flash (Vision)", "Extracts Visual Scenes", 12, 85, 115, 60, colors.HexColor("#DBEAFE"), colors.HexColor("#1E40AF")),
        ("2. Scriptwriter Agent", "gemini-3.7-flash (Persona)", "Drafts Alex & Sam Banter", 145, 85, 120, 60, colors.HexColor("#FEF3C7"), colors.HexColor("#92400E")),
        ("3. QA Auditor Agent", "Forensic Evaluator", "Verifies Zero Timestamps", 283, 85, 120, 60, colors.HexColor("#FEE2E2"), colors.HexColor("#991B1B")),
        ("4. Chronos Sync", "TTS PCM Metering", "duration = bytes / 48", 418, 85, 110, 60, colors.HexColor("#DCFCE7"), colors.HexColor("#166534")),
    ]

    for title, tech, role, x, y, w, h, bg_c, text_c in agent_boxes:
        d_agents.add(Rect(x, y, w, h, fillColor=bg_c, strokeColor=BORDER_COLOR, strokeWidth=1, rx=4, ry=4))
        d_agents.add(String(x + w/2, y + h - 14, title, textAnchor='middle', fontName='Helvetica-Bold', fontSize=8.5, fillColor=text_c))
        d_agents.add(String(x + w/2, y + h - 27, tech, textAnchor='middle', fontName='Helvetica', fontSize=7, fillColor=SECONDARY))
        d_agents.add(String(x + w/2, y + 10, role, textAnchor='middle', fontName='Helvetica-Oblique', fontSize=7, fillColor=TEXT_MUTED))

    # Forward Workflow Arrows
    for arrow_x in [128, 266, 404]:
        d_agents.add(Line(arrow_x, 115, arrow_x + 16, 115, strokeColor=ACCENT_BLUE, strokeWidth=1.5))
        d_agents.add(Line(arrow_x + 12, 118, arrow_x + 16, 115, strokeColor=ACCENT_BLUE, strokeWidth=1.5))
        d_agents.add(Line(arrow_x + 12, 112, arrow_x + 16, 115, strokeColor=ACCENT_BLUE, strokeWidth=1.5))

    # Adversarial Feedback Loop (QA -> Scriptwriter)
    d_agents.add(Line(343, 85, 343, 62, strokeColor=ACCENT_AMBER, strokeWidth=1.5))
    d_agents.add(Line(343, 62, 205, 62, strokeColor=ACCENT_AMBER, strokeWidth=1.5))
    d_agents.add(Line(205, 62, 205, 83, strokeColor=ACCENT_AMBER, strokeWidth=1.5))
    d_agents.add(Line(202, 80, 205, 84, strokeColor=ACCENT_AMBER, strokeWidth=1.5))
    d_agents.add(Line(208, 80, 205, 84, strokeColor=ACCENT_AMBER, strokeWidth=1.5))
    d_agents.add(String(274, 52, "Adversarial Loop: Refine dialogue if QA Score < 85%", textAnchor='middle', fontName='Helvetica-Bold', fontSize=7, fillColor=ACCENT_AMBER))

    # Lower Pipeline Stage: Compiler Agent & Observability
    d_agents.add(Rect(60, 10, 195, 36, fillColor=colors.HexColor("#F3E8FF"), strokeColor=BORDER_COLOR, strokeWidth=1, rx=4, ry=4))
    d_agents.add(String(157, 30, "5. Compiler Agent (FFmpeg Engine)", textAnchor='middle', fontName='Helvetica-Bold', fontSize=8, fillColor=ACCENT_PURPLE))
    d_agents.add(String(157, 18, "Stitches 1080p MP4 with permanent holds", textAnchor='middle', fontName='Helvetica', fontSize=7, fillColor=SECONDARY))

    d_agents.add(Rect(285, 10, 195, 36, fillColor=colors.HexColor("#EDE9FE"), strokeColor=BORDER_COLOR, strokeWidth=1, rx=4, ry=4))
    d_agents.add(String(382, 30, "6. Observability: ClickHouse + Grafana", textAnchor='middle', fontName='Helvetica-Bold', fontSize=8, fillColor=ACCENT_PURPLE))
    d_agents.add(String(382, 18, "Logs turn_index, audio_duration_ms & freeze offsets", textAnchor='middle', fontName='Helvetica', fontSize=7, fillColor=SECONDARY))

    # Chronos connections to lower components
    d_agents.add(Line(473, 85, 473, 28, strokeColor=ACCENT_GREEN, strokeWidth=1.2))
    d_agents.add(Line(473, 28, 481, 28, strokeColor=ACCENT_GREEN, strokeWidth=1.2))
    d_agents.add(Line(418, 115, 256, 28, strokeColor=ACCENT_GREEN, strokeWidth=1.2))

    story.append(d_agents)
    story.append(Spacer(1, 8))

    # Collaboration Matrix Table
    collab_data = [
        [Paragraph("Agent / Engine", table_header_style), Paragraph("Input Assets", table_header_style), Paragraph("Agent Responsibility & Output Artifact", table_header_style)],
        [
            Paragraph("<b>Ingestion Agent</b>", table_cell_bold),
            Paragraph("Raw <code>.mp4</code> + <code>README.md</code>", table_cell_style),
            Paragraph("Analyzes video pixels via Gemini File API; decomposes screencast into millisecond Visual Scenes with action-reaction causality.", table_cell_style)
        ],
        [
            Paragraph("<b>Scriptwriter Agent</b>", table_cell_bold),
            Paragraph("Visual Scenes + README Concepts", table_cell_style),
            Paragraph("Generates natural conversational banter between Alex (Systems Architect) and Sam (UX Lead); budgets speech words to scene duration (~2.5 words/s).", table_cell_style)
        ],
        [
            Paragraph("<b>QA & Pacing Auditor</b>", table_cell_bold),
            Paragraph("Scenes + Draft Dialogue", table_cell_style),
            Paragraph("Audits alignment, checks README grounding, and guarantees 100% elimination of robotic synthetic timestamps. Triggers refinement pass on defect.", table_cell_style)
        ],
        [
            Paragraph("<b>Chronos Sync Engine</b>", table_cell_bold),
            Paragraph("Approved Script + Visual Scenes", table_cell_style),
            Paragraph("Synthesizes 24 kHz raw PCM, meters duration ($48\text{ bytes/ms}$), calculates <code>required_freeze_ms</code>, and dispatches ClickHouse events.", table_cell_style)
        ]
    ]

    t_collab = Table(collab_data, colWidths=[120, 140, 280])
    t_collab.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_collab)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: HEXAGONAL ARCHITECTURE (PORTS & ADAPTERS)
    # =========================================================================
    story.append(Paragraph("3. Hexagonal Architecture (Ports & Adapters Specification)", h1_style))
    story.append(Paragraph(
        "Frame Talk is architected strictly upon <b>Hexagonal Architecture (Ports & Adapters)</b>. "
        "The Core Domain (synchronization mathematics, agent choreography, pacing logic) is isolated from external frameworks, "
        "databases, and model APIs. This guarantees testability, modular vendor independence, and graceful fallback modes.",
        body_style
    ))
    story.append(Spacer(1, 5))

    # --- Hexagonal Architecture Vector Diagram ---
    d_hex = Drawing(540, 190)
    d_hex.add(Rect(0, 0, 540, 190, fillColor=BG_LIGHT, strokeColor=BORDER_COLOR, strokeWidth=1, rx=6, ry=6))

    # Layer 1: Driving Adapters (Left)
    d_hex.add(Rect(10, 25, 95, 145, fillColor=colors.HexColor("#EFF6FF"), strokeColor=colors.HexColor("#93C5FD"), strokeWidth=1, rx=5, ry=5))
    d_hex.add(String(57, 155, "DRIVING ADAPTERS", textAnchor='middle', fontName='Helvetica-Bold', fontSize=7.5, fillColor=ACCENT_BLUE))
    d_hex.add(String(57, 142, "(Primary / Inbound)", textAnchor='middle', fontName='Helvetica', fontSize=6.5, fillColor=TEXT_MUTED))
    d_hex.add(Rect(16, 105, 83, 30, fillColor=colors.white, strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=3, ry=3))
    d_hex.add(String(57, 122, "Web Browser SPA", textAnchor='middle', fontName='Helvetica-Bold', fontSize=7, fillColor=PRIMARY))
    d_hex.add(String(57, 112, "Canvas / Chronos Player", textAnchor='middle', fontName='Helvetica', fontSize=6, fillColor=SECONDARY))
    d_hex.add(Rect(16, 68, 83, 30, fillColor=colors.white, strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=3, ry=3))
    d_hex.add(String(57, 85, "FastAPI REST API", textAnchor='middle', fontName='Helvetica-Bold', fontSize=7, fillColor=PRIMARY))
    d_hex.add(String(57, 75, "HTTP Controllers", textAnchor='middle', fontName='Helvetica', fontSize=6, fillColor=SECONDARY))
    d_hex.add(Rect(16, 32, 83, 30, fillColor=colors.white, strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=3, ry=3))
    d_hex.add(String(57, 49, "CLI Evals & Tests", textAnchor='middle', fontName='Helvetica-Bold', fontSize=7, fillColor=PRIMARY))
    d_hex.add(String(57, 39, "run_all_evals.py", textAnchor='middle', fontName='Helvetica', fontSize=6, fillColor=SECONDARY))

    # Layer 2: Inbound Ports
    d_hex.add(Rect(114, 35, 80, 125, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#CBD5E1"), strokeWidth=1, rx=4, ry=4))
    d_hex.add(String(154, 148, "INBOUND PORTS", textAnchor='middle', fontName='Helvetica-Bold', fontSize=7, fillColor=SECONDARY))
    inbound_ports = ["IngestPort", "ScriptPort", "AudioPort", "CompilePort", "TelemetryPort"]
    for i, port in enumerate(inbound_ports):
        py = 126 - (i * 20)
        d_hex.add(Rect(118, py, 72, 16, fillColor=colors.HexColor("#E2E8F0"), strokeColor=colors.white, strokeWidth=0.5, rx=2, ry=2))
        d_hex.add(String(154, py + 4, port, textAnchor='middle', fontName='Courier-Bold', fontSize=6.5, fillColor=PRIMARY))

    # Layer 3: Core Domain (Hexagon Center)
    d_hex.add(Rect(202, 15, 140, 165, fillColor=colors.HexColor("#FEF3C7"), strokeColor=ACCENT_AMBER, strokeWidth=1.5, rx=6, ry=6))
    d_hex.add(String(272, 167, "CORE DOMAIN", textAnchor='middle', fontName='Helvetica-Bold', fontSize=9, fillColor=colors.HexColor("#92400E")))
    d_hex.add(String(272, 156, "(The Hexagon Center)", textAnchor='middle', fontName='Helvetica', fontSize=6.5, fillColor=colors.HexColor("#B45309")))
    # Domain Entities Box
    d_hex.add(Rect(208, 92, 128, 58, fillColor=colors.white, strokeColor=colors.HexColor("#FDE68A"), strokeWidth=1, rx=3, ry=3))
    d_hex.add(String(272, 138, "Domain Entities & Models", textAnchor='middle', fontName='Helvetica-Bold', fontSize=7.5, fillColor=PRIMARY))
    d_hex.add(String(272, 126, "• VisualScene (boundaries, actions)", textAnchor='middle', fontName='Helvetica', fontSize=6.5, fillColor=SECONDARY))
    d_hex.add(String(272, 114, "• DialogueTurn (speaker, duration)", textAnchor='middle', fontName='Helvetica', fontSize=6.5, fillColor=SECONDARY))
    d_hex.add(String(272, 102, "• ChronosSchedule (freeze math)", textAnchor='middle', fontName='Helvetica', fontSize=6.5, fillColor=SECONDARY))
    # Domain Services Box
    d_hex.add(Rect(208, 24, 128, 62, fillColor=colors.white, strokeColor=colors.HexColor("#FDE68A"), strokeWidth=1, rx=3, ry=3))
    d_hex.add(String(272, 74, "Core Engines & Logic", textAnchor='middle', fontName='Helvetica-Bold', fontSize=7.5, fillColor=PRIMARY))
    d_hex.add(String(272, 62, "• Chronos Sync Math (48 B/ms)", textAnchor='middle', fontName='Helvetica', fontSize=6.5, fillColor=SECONDARY))
    d_hex.add(String(272, 50, "• Timeline Dynamic Holds (+300ms)", textAnchor='middle', fontName='Helvetica', fontSize=6.5, fillColor=SECONDARY))
    d_hex.add(String(272, 38, "• Prompt Guardrails & XML Wrapping", textAnchor='middle', fontName='Helvetica', fontSize=6.5, fillColor=SECONDARY))

    # Layer 4: Outbound Ports
    d_hex.add(Rect(350, 35, 82, 125, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#CBD5E1"), strokeWidth=1, rx=4, ry=4))
    d_hex.add(String(391, 148, "OUTBOUND PORTS", textAnchor='middle', fontName='Helvetica-Bold', fontSize=7, fillColor=SECONDARY))
    outbound_ports = ["ModelPort", "SpeechPort", "StoragePort", "JobPort", "MetricsPort"]
    for i, port in enumerate(outbound_ports):
        py = 126 - (i * 20)
        d_hex.add(Rect(355, py, 72, 16, fillColor=colors.HexColor("#E2E8F0"), strokeColor=colors.white, strokeWidth=0.5, rx=2, ry=2))
        d_hex.add(String(391, py + 4, port, textAnchor='middle', fontName='Courier-Bold', fontSize=6.5, fillColor=PRIMARY))

    # Layer 5: Driven Adapters (Right)
    d_hex.add(Rect(439, 20, 93, 155, fillColor=colors.HexColor("#F0FDF4"), strokeColor=colors.HexColor("#86EFAC"), strokeWidth=1, rx=5, ry=5))
    d_hex.add(String(485, 165, "DRIVEN ADAPTERS", textAnchor='middle', fontName='Helvetica-Bold', fontSize=7.5, fillColor=ACCENT_GREEN))
    d_hex.add(String(485, 153, "(Secondary / Outbound)", textAnchor='middle', fontName='Helvetica', fontSize=6.5, fillColor=TEXT_MUTED))
    d_hex.add(Rect(444, 120, 83, 26, fillColor=colors.white, strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=3, ry=3))
    d_hex.add(String(485, 134, "Gemini 3.7 Flash", textAnchor='middle', fontName='Helvetica-Bold', fontSize=7, fillColor=PRIMARY))
    d_hex.add(String(485, 125, "Vision & Script API", textAnchor='middle', fontName='Helvetica', fontSize=6, fillColor=SECONDARY))
    d_hex.add(Rect(444, 88, 83, 26, fillColor=colors.white, strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=3, ry=3))
    d_hex.add(String(485, 102, "Gemini TTS Preview", textAnchor='middle', fontName='Helvetica-Bold', fontSize=7, fillColor=PRIMARY))
    d_hex.add(String(485, 93, "24 kHz PCM Audio", textAnchor='middle', fontName='Helvetica', fontSize=6, fillColor=SECONDARY))
    d_hex.add(Rect(444, 56, 83, 26, fillColor=colors.white, strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=3, ry=3))
    d_hex.add(String(485, 70, "ClickHouse Server", textAnchor='middle', fontName='Helvetica-Bold', fontSize=7, fillColor=PRIMARY))
    d_hex.add(String(485, 61, "Time-Series sync_events", textAnchor='middle', fontName='Helvetica', fontSize=6, fillColor=SECONDARY))
    d_hex.add(Rect(444, 25, 83, 26, fillColor=colors.white, strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=3, ry=3))
    d_hex.add(String(485, 38, "FFmpeg Subprocess", textAnchor='middle', fontName='Helvetica-Bold', fontSize=7, fillColor=PRIMARY))
    d_hex.add(String(485, 29, "Concat & Freeze Loops", textAnchor='middle', fontName='Helvetica', fontSize=6, fillColor=SECONDARY))

    # Horizontal Connecting Arrows
    d_hex.add(Line(105, 97, 114, 97, strokeColor=ACCENT_BLUE, strokeWidth=1.5))
    d_hex.add(Line(194, 97, 202, 97, strokeColor=ACCENT_BLUE, strokeWidth=1.5))
    d_hex.add(Line(342, 97, 350, 97, strokeColor=ACCENT_GREEN, strokeWidth=1.5))
    d_hex.add(Line(432, 97, 439, 97, strokeColor=ACCENT_GREEN, strokeWidth=1.5))

    story.append(d_hex)
    story.append(Spacer(1, 8))

    hex_data = [
        [Paragraph("Hexagonal Component", table_header_style), Paragraph("Interface / Port Contract", table_header_style), Paragraph("Architectural Decoupling Benefit", table_header_style)],
        [
            Paragraph("<b>Core Domain Logic</b>", table_cell_bold),
            Paragraph("Zero external dependencies; pure Python", table_cell_style),
            Paragraph(r"The Chronos dynamic video hold mathematics ($\text{pcm\_bytes}/48$) and pacing algorithms are completely decoupled from Google Gemini and can run offline in unit tests.", table_cell_style)
        ],
        [
            Paragraph("<b>Driving Adapters</b>", table_cell_bold),
            Paragraph("FastAPI, ChronosPlayer Canvas, CLI", table_cell_style),
            Paragraph("Enables browser SPA, background workers, and automated test runners to drive the studio without coupling the domain to HTTP mechanics.", table_cell_style)
        ],
        [
            Paragraph("<b>Driven Adapters</b>", table_cell_bold),
            Paragraph("Gemini Client, ClickHouse, FFmpeg, Files", table_cell_style),
            Paragraph("All external I/O sits behind ports. If ClickHouse is unavailable, an in-memory ring buffer adapter engages automatically without crashing the studio.", table_cell_style)
        ]
    ]

    t_hex = Table(hex_data, colWidths=[120, 150, 270])
    t_hex.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0F766E")),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_hex)

    story.append(PageBreak())

    # =========================================================================
    # PAGE 3: CHRONOS MATH + OBSERVABILITY + SECURITY + DEPLOYMENT
    # =========================================================================
    story.append(Paragraph("4. Chronos Mathematical Synchronization Model", h1_style))
    story.append(Paragraph(
        "<b>1. Exact PCM Duration Metering:</b> For 24 kHz, 16-bit Mono audio, 48,000 bytes equal 1.0 second. Speech duration is exact:<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;<b>duration_ms = (len(pcm_bytes) / 48000) * 1000 = len(pcm_bytes) / 48</b><br/>"
        "<b>2. Dynamic Visual Hold (Video Timeline Stretch):</b> If speech duration exceeds the raw scene length:<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;<b>total_speech_ms = sum(turn.duration_ms) + max(0, N - 1) * 220ms</b><br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;<b>required_freeze_ms = max(0, total_speech_ms - scene_duration_ms + 300ms)</b><br/>"
        "The $+300\text{ms}$ visual buffer ensures the viewer comfortably absorbs the visual state after the last spoken syllable.",
        body_style
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("5. Partner Track: ClickHouse Columnar Logging & Grafana Labs", h1_style))
    story.append(Paragraph(
        "To fulfill hackathon partner requirements, every synthesis turn logs time-series micro-events to <b>ClickHouse</b> "
        "(<code>castops.sync_events</code>), monitored live via <b>Grafana</b> at <code>https://grafana.taskmind-ai.com</code>:",
        body_style
    ))
    story.append(Spacer(1, 4))

    ch_data = [
        [Paragraph("Table Name", table_header_style), Paragraph("Key Columns & Schema", table_header_style), Paragraph("Observability Purpose", table_header_style)],
        [Paragraph("<code>castops.sync_events</code>", table_cell_bold), Paragraph("<code>event_time, speaker, dialogue_text, audio_duration_ms, required_freeze_ms, accumulated_drift_ms</code>", table_cell_style), Paragraph("Tracks timeline freeze offsets and audio-video lockstep per dialogue turn.", table_cell_style)],
        [Paragraph("<code>castops.llm_calls</code>", table_cell_bold), Paragraph("<code>call_time, model_name, agent_name, prompt_tokens, cached_tokens, completion_tokens, cost_usd</code>", table_cell_style), Paragraph("Tracks granular model telemetry, latencies, and 75% Google prompt cache discounts.", table_cell_style)],
        [Paragraph("<code>castops.user_activity</code>", table_cell_bold), Paragraph("<code>event_time, user_hash, action_type, session_id</code>", table_cell_style), Paragraph("GDPR-compliant zero-PII conversion funnel (VIDEO_ANALYZED -> SCRIPT -> AUDIO).", table_cell_style)]
    ]

    t_ch = Table(ch_data, colWidths=[125, 235, 180])
    t_ch.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4A1D96")),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(t_ch)
    story.append(Spacer(1, 6))

    story.append(Paragraph("6. Production Cyber Security & Ephemeral Storage", h1_style))
    sec_data = [
        [Paragraph("Security Layer", table_header_style), Paragraph("Defense Mechanism & Implementation", table_header_style)],
        [Paragraph("<b>Indirect Injection Defense</b>", table_cell_bold), Paragraph("Sanitization filters strip instruction overrides. README documentation is isolated within <code>&lt;untrusted_documentation&gt;</code> wrappers with strict system directives.", table_cell_style)],
        [Paragraph("<b>Anti-Injection Scope Lock</b>", table_cell_bold), Paragraph("Hardened system instructions in Google ADK agent.py enforce explicit refusal (<code>ACCESS DENIED</code>) on jailbreak attempts.", table_cell_style)],
        [Paragraph("<b>Path Traversal Immunity</b>", table_cell_bold), Paragraph("<code>_safe_resolve()</code> enforces strict folder boundaries, stripping <code>..</code>, forward/backward slashes, and regex-validating upload identifiers.", table_cell_style)],
        [Paragraph("<b>SQL Injection Immunity</b>", table_cell_bold), Paragraph("All ClickHouse queries use parameterized bindings (<code>%(session_id)s</code>) with strict type coercion and integer bounds checking.", table_cell_style)],
        [Paragraph("<b>Anonymous User Isolation</b>", table_cell_bold), Paragraph("Clients generate an anonymous UUID stored in IndexedDB. Backend hashes this with SHA-256 + salt; all job queries enforce user ownership.", table_cell_style)],
        [Paragraph("<b>Bring Your Own Key (BYOK)</b>", table_cell_bold), Paragraph("Client API keys are kept in browser <code>localStorage</code> and passed in transient headers, never persisted to server disk or database.", table_cell_style)],
        [Paragraph("<b>Production Security Headers</b>", table_cell_bold), Paragraph("ASGI middleware injects <code>X-Content-Type-Options: nosniff</code>, <code>X-Frame-Options: SAMEORIGIN</code>, and CSP headers.", table_cell_style)],
    ]
    t_sec = Table(sec_data, colWidths=[140, 400])
    t_sec.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BG_LIGHT),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    story.append(t_sec)
    story.append(Spacer(1, 6))

    story.append(Paragraph("7. Production VPS Deployment & Dual Verification Matrix", h1_style))
    story.append(Paragraph(
        f"<b>Production Deployment:</b> Nginx reverse proxy routes <code>{config.app_url}</code> to FastAPI (port 8000) "
        f"and <code>{config.grafana_url}</code> to Grafana (port 3004). Docker Compose runs ClickHouse (1.5 GB limit, bound to <code>127.0.0.1:8123</code>) "
        "and Grafana (512 MB limit with anonymous viewer access).<br/><br/>"
        "<b>Verification Matrix:</b><br/>"
        "• <b>4-Tier AI Evals (<code>server/evals/</code>):</b> Benchmarks entity recall (&ge; 70%), causality (&ge; 85%), QA discrimination, and GCP Director Agent execution (<b>Score: 94/100</b>).<br/>"
        "• <b>Automated Unit Tests & Quality Gates:</b> 37 zero-dependency unit tests running in <b>0.68 seconds</b> with automated HTML DOM stack balancing and git pre-commit hooks.",
        body_style
    ))

    doc.build(story)
    print(f"Successfully generated {OUTPUT_PDF}")

if __name__ == "__main__":
    build_architecture_pdf()
