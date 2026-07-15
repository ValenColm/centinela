# Errores encontrados y soluciones

## 1. Cuota insuficiente para App Service Plan (Bicep)

**Error:** `SubscriptionIsOverQuotaForSku` al intentar crear un App Service Plan desde Bicep
**Causa:** La suscripción gratuita tiene cuota 0 para Total VMs en ciertas regiones
**Solución:** 
- Se quitó el App Service Plan y las Functions del Bicep
- Se crean via CLI con `--consumption-plan-location westus` que deja que Azure cree el plan automáticamente
- El plan se crea solo con el nombre `WestUSLinuxDynamicPlan`
- **Referencia:** commit `827ad74` y `c01620a`, script `create-functions.sh`

## 2. Service Principal sin permisos para asignar roles

**Error:** `AuthorizationFailed` al intentar crear `Microsoft.Authorization/roleAssignments` desde Bicep
**Causa:** El Service Principal `sp-centinela-github` tiene rol Contributor pero NO tiene `Microsoft.Authorization/roleAssignments/write`
**Solución:**
- Se quitaron los roleAssignments del Bicep
- Se asignan manualmente via CLI después de crear las Functions
- La asignación se hace desde la sesión personal de Azure (Valentina), no desde el SP
- **Referencia:** commit `bd1b065`, líneas 42-51 de `create-functions.sh`

## 3. Firewall de Storage bloqueaba creación de Functions

**Error:** `StorageAccountVirtualNetworkRuleError` al crear Function App con `--storage-account`
**Causa:** El Storage tenía `networkAcls.defaultAction: Deny`, lo que impedía que el servicio de Functions provisioning accediera
**Solución:**
- Se cambió a `defaultAction: Allow` + `bypass: AzureServices`
- Esto permite que servicios Azure (incluyendo Functions provisioning) accedan al Storage
- La seguridad ahora depende de Managed Identity + RBAC, no del firewall de red
- **Referencia:** commit `81d2179` y `473763b`, línea 15-18 de `main.bicep`

## 4. HTTPS forzado con comando incorrecto

**Error:** `az functionapp config set --https-only true` falló con error de argumento inválido
**Causa:** `az functionapp config set` NO tiene el flag `--https-only`
**Solución:**
- Usar `az functionapp update --name <name> --resource-group <rg> --set httpsOnly=true`
- También funciona `az functionapp update -n <name> -g <rg> -H httpsOnly true`
- **Referencia:** commit `93c9bfa`, líneas 53-55 de `create-functions.sh`

## 5. Nombre de recursos inválido por sufijo UUID muy largo

**Error:** Nombres de Storage Account excedían los 24 caracteres o contenían caracteres inválidos
**Causa:** `uniqueString()` genera hashes largos (13+ chars), y al combinarlos con prefijos se exceden límites
**Solución:**
- Usar `substring(uniqueString(resourceGroup().id), 0, 6)` para truncar a 6 caracteres
- Los nombres quedan como `stcentinelaXXXXXX` y `kv-centinela-XXXXXX`
- **Referencia:** commit `e35787b`

## 6. Location incorrecta

**Error:** Algunos recursos no estaban disponibles en `eastus` para la suscripción gratuita
**Solución:** Cambiar todo a `westus`
- **Referencia:** commit `3a94bf4`

## 7. Extension `application-insights` no instalada en Azure CLI

**Error:** `The command requires the extension application-insights` al ejecutar `az monitor app-insights component show`
**Causa:** La extensión no viene preinstalada en todas las versiones de Azure CLI
**Solución:** El CLI pregunta automáticamente si instalar la extensión. Responder `y`. O preinstalarla con:
```bash
az extension add --name application-insights --allow-preview false
```
Para evitar que pregunte en el futuro:
```bash
az config set extension.use_dynamic_install=yes_without_prompt
```

## 8. Application Insights no se vinculó automáticamente a las Functions

**Warning:** `Error while trying to create and configure an Application Insights` al crear Functions
**Causa:** El flag `--application-insights` requiere que App Insights esté en el mismo RG y región (lo está) pero aparentemente falló por temas de permisos/provisioning concurrente
**Solución pendiente:** Vincular manualmente desde portal o CLI con:
```bash
az functionapp config appsettings set --name func-api-<suffix> -g rg-centinela \
  --settings APPINSIGHTS_INSTRUMENTATIONKEY=<ikey> APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=<ikey>"
```
