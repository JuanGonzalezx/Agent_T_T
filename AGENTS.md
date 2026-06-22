# AGENTS.md — Agent_T_T (Talento Tech) · 🔵 REFERENCIA CONGELADA

> Backend del agente virtual de **Talento Tech**. **Proyecto cerrado / producción histórica.** Fue el motor del que nació `Regionalizacion/`. Probado en producción: la secretaría envió mensajes masivos a ~800 estudiantes.
> **No desarrollar features nuevas aquí.** Es banco de piezas probadas y referencia de arquitectura.

---

## Para qué sirve este repo hoy

1. **Referencia de arquitectura** para Regionalización (mismo stack, más features).
2. **Banco de piezas reutilizables** ya probadas: `whatsapp_service.py`, `webhook_controller.py`, `message_dedup.py`, `gemini_logger.py`, controllers de campañas/citas/eventos.
3. Soporta el panel de la secretaría (`Panel_Agent_TT`) y el deploy en `agent-t-t.onrender.com`.

## Stack

Flask + Gunicorn · Turso/libSQL · LangGraph + Gemini 2.5 Flash Lite · APScheduler · Google Drive · WhatsApp Cloud API · Render.

## Diferencias vs. Regionalización

Agent_T_T cubre el caso Talento Tech **completo**: campañas (MATRICULA/EVENTO/INFO), confirmación de matrícula, gestión de eventos, citas, notas. Regionalización tomó el subconjunto "consulta académica" y lo especializó para U en tu Pueblo con un modelo de datos relacional (subregiones→municipios→programas→módulos→rendimiento).

## Deuda técnica documentada (si algún día se retoma)

- **Modelo "tabla plana" original** de estudiantes vs. el modelo relacional de Regionalización. Si se quiere unificar, migrar TT al schema relacional nuevo.
- **Lógica de campañas acoplada** a Excel plano; el diseño relacional de `campana_miembros` (ver `docs/estrategia/MVP_FUNCIONES`) lo limpia.
- **Cold-start de Render (free)** causó la queja "el sistema no fue eficiente". Para cualquier demo: warm-up previo o plan pago.
- Cambios sin commitear en working tree (`.env.example`, docs `FRONTEND_*`). Revisar y commitear o descartar antes de archivar.

## Reglas

- **Solo lectura/copia.** Si necesitas una pieza en Regionalización, **cópiala allá**, no la edites aquí esperando que afecte al proyecto activo.
- Secretos solo en `.env` (gitignored).
