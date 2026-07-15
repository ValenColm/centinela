# Pendiente de Valentina — esta semana

## 1. Unificar deploy.sh para que reconstruya todo desde cero

Actualmente `deploy.sh` solo corre Bicep. Las Functions se crean con `create-functions.sh` aparte.

**Tarea:** Integrar `create-functions.sh` al final de `deploy.sh` para que `bash deploy.sh` reconstruya TODO.

```bash
# Al final de deploy.sh, después del deploy de Bicep:
echo "=== Creando Functions vía CLI ==="
bash "$(dirname "$0")/create-functions.sh"
```

## 2. App Settings de las Functions ✅

Configuradas el 14/07/2026. Settings aplicadas a ambas Functions:
- `AZURE_STORAGE_ACCOUNT=stcentinelaufwhov`
- `KEY_VAULT_URI=https://kv-centinela-ufwhov.vault.azure.net`
- `AzureWebJobsStorage__accountName=stcentinelaufwhov`
- `APPINSIGHTS_INSTRUMENTATIONKEY=808ded26-4859-48f9-8cf5-37d6b169676d`
- `APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=808ded26-4859-48f9-8cf5-37d6b169676d`

## 3. Vincular Application Insights a las Functions ✅

Vinculado vía App Insights key en App Settings (arriba). Ambas Functions ya envían telemetría a `appi-centinela-ufwhov`.

---

Las Functions necesitan variables de entorno para funcionar. Configurar con:

```bash
STORAGE_ACCOUNT="stcentinelaufwhov"
KV_URI="https://kv-centinela-ufwhov.vault.azure.net"

az functionapp config appsettings set --name func-api-<suffix> -g rg-centinela \
  --settings \
    AZURE_STORAGE_ACCOUNT=$STORAGE_ACCOUNT \
    KEY_VAULT_URI=$KV_URI \
    AzureWebJobsStorage__accountName=$STORAGE_ACCOUNT

az functionapp config appsettings set --name func-scoring-<suffix> -g rg-centinela \
  --settings \
    AZURE_STORAGE_ACCOUNT=$STORAGE_ACCOUNT \
    KEY_VAULT_URI=$KV_URI \
    AzureWebJobsStorage__accountName=$STORAGE_ACCOUNT
```

Para referenciar el secreto de Key Vault (la forma moderna con Managed Identity):
```
@Microsoft.KeyVault(SecretUri=https://kv-centinela-ufwhov.vault.azure.net/secrets/StorageConnectionString)
```

## 3. Vincular Application Insights a las Functions

```bash
APPI_KEY=$(az monitor app-insights component show --app appi-centinela-ufwhov -g rg-centinela --query instrumentationKey -o tsv)
APPI_CONN=$(az monitor app-insights component show --app appi-centinela-ufwhov -g rg-centinela --query connectionString -o tsv)

az functionapp config appsettings set --name func-api-<suffix> -g rg-centinela \
  --settings \
    APPINSIGHTS_INSTRUMENTATIONKEY=$APPI_KEY \
    APPLICATIONINSIGHTS_CONNECTION_STRING=$APPI_CONN

az functionapp config appsettings set --name func-scoring-<suffix> -g rg-centinela \
  --settings \
    APPINSIGHTS_INSTRUMENTATIONKEY=$APPI_KEY \
    APPLICATIONINSIGHTS_CONNECTION_STRING=$APPI_CONN
```

## 4. Probar deploy completo desde cero

```bash
# Eliminar RG (cuidado: borra todo)
az group delete --name rg-centinela --yes --no-wait

# Esperar a que termine y volver a crear
bash infra/deploy.sh
```

## Resumen

| # | Tarea | Prioridad |
|---|-------|-----------|
| 1 | Integrar `create-functions.sh` en `deploy.sh` | Alta |
| 2 | Configurar App Settings en ambas Functions | ✅ Hecho |
| 3 | Vincular Application Insights a Functions | ✅ Hecho |
| 4 | Probar deploy completo desde cero | Alta |

Después de esto, arrancar con **Semana 3**:
- Dashboards en Application Insights (transacciones/min, casos abiertos, errores)
- Alertas (errores > X en 5 min → email)
- Key Vault logging (auditar lecturas de secretos)
