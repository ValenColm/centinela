# Pendiente de Valentina — completado

## ✅ Todo lo de Semana 1 y 2 está listo

| Tarea | Estado | Notas |
|-------|--------|-------|
| Unificar deploy.sh | ✅ | `deploy.sh` ahora llama a `create-functions.sh` |
| App Settings | ✅ | AZURE_STORAGE_ACCOUNT, KEY_VAULT_URI, AzureWebJobsStorage__accountName, APPINSIGHTS_INSTRUMENTATIONKEY |
| Application Insights vinculado | ✅ | Ambas Functions apuntan a `appi-centinela-ufwhov` |
| HTTPS forzado | ✅ | `httpsOnly: true` en ambas |
| Roles RBAC | ✅ | Storage Table + Queue Data Contributor, Key Vault Secrets User |
| Script con retry | ✅ | Sleep 30s + reintentos para propagación de identidad |
| disable-app-insights | ✅ | Evita crear App Insights duplicados por Function |
| Probar deploy desde cero | ✅ | `bash infra/deploy.sh` completado exitosamente |
| Documentación | ✅ | `docs/` con infra, errores y pendientes |

## Recursos actuales (post-deploy)

- Storage: `stcentinelaufwhov`
- Key Vault: `kv-centinela-ufwhov`
- App Insights: `appi-centinela-ufwhov`
- Log Analytics: `log-centinela-ufwhov`
- Function API: `func-api-1784119485`
- Function Scoring: `func-scoring-1784119485`

## Próximos pasos (Semana 3)

Cuando el equipo avance:
- Dashboards en Application Insights (transacciones/min, casos abiertos, errores)
- Alertas (errores > X en 5 min → email)
- Key Vault logging (auditar lecturas de secretos)
- Validar deploy desde cero con un solo comando

## Para el equipo

Ya pueden clonar y arrancar:
```bash
git clone https://github.com/ValenColm/centinela.git
cd centinela
git checkout -b <su-rama>
```
