# Plan de prueba: pipeline multiagente para creación de videos

## Objetivo

Validar que Copilot/Codex puede orquestar a Kilo y Cline para diseñar un
pipeline de video reproducible, sin modificar el proyecto principal ni usar
servicios de pago automáticamente.

## Sandbox

`data/video_skill_sandbox/` es el workspace de prueba. Las tareas sólo pueden
crear informes Markdown y JSON dentro de ese directorio.

## Roles

1. Agente principal: define el contrato, revisa evidencia y decide qué skills
   instalar.
2. Kilo: analiza la arquitectura del pipeline audiovisual y propone etapas.
3. Cline: verifica el inventario de skills, compatibilidad y riesgos de uso.
4. Evaluador: comprueba que ambos informes existan, sean legibles y no
   contengan credenciales ni comandos destructivos.

## Skills candidatas

- `speech`: narración y síntesis de voz.
- `transcribe`: subtítulos y transcripción.
- `playwright`: automatización de herramientas web autorizadas.
- `screenshot`: captura de imágenes para storyboard o evidencias.

La instalación será explícita y posterior a la revisión. No se instalarán
skills por similitud de nombre ni desde repositorios no verificados.

## Criterios de aceptación

- Kilo y Cline producen un informe dentro del sandbox.
- Cada informe contiene entradas, salidas, dependencias y riesgos.
- El evaluador detecta archivos fuera del sandbox.
- No se habilita generación de video real ni publicación automática.
- El plan puede reanudarse sin perder sus resultados.

## Estado

- [x] Inventario oficial de skills consultado.
- [x] Sandbox y contrato definidos.
- [ ] Ejecutar análisis Kilo.
- [ ] Ejecutar verificación Cline.
- [ ] Evaluar informes.
- [ ] Solicitar aprobación para instalar skills candidatas.
