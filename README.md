# ITFlow Linux Agent

Zelfstandige, headless Debian/Linux-agent die lokale hardware-, OS- en
netwerkgegevens synchroniseert met ITFlow. Dit project bevat geen Windows-code
en voert geen GUI-, registry-, DPAPI-, Active Directory- of hostname-renamewerk
uit.

## Functionaliteit

- inventaris uit Linux DMI, `/proc`, `/sys`, `/etc/os-release`, `ip` en `lsblk`;
- matching op gevalideerde hardware-serial en geconfigureerde `client_id`;
- globale serialzoekactie en optioneel volgen van een clienttransfer;
- create en minimale update van ITFlow-assets;
- enrollment- en transfertickets met fallback voor oudere ITFlow-versies;
- lokale, atomisch geschreven state en een sysinfo-snapshot;
- logging naar stdout/stderr en daardoor automatisch naar journald;
- niet-muterende `--test`/`--dry-run`-modus;
- hourly systemd timer met persistent catch-up en randomized delay;
- unit tests voor identiteit, configuratie, inventory, API en syncflows.

## Ondersteuning

- Debian 12 of nieuwer;
- Python 3.11 of nieuwer;
- systemd;
- een ITFlow API-key die de benodigde client(s) mag lezen en schrijven;
- `iproute2` en `util-linux`.

Voor transfer-following is een all-clients API-key nodig. Met een
clientgebonden key moet `follow_transfers = false` worden gebruikt.

## ITFlow API-contract

De agent gebruikt:

| Endpoint | Methode | Gebruik |
|---|---|---|
| `assets/read.php` | GET | probe en lookup op serial/client |
| `assets/create.php` | POST | enrollment |
| `assets/update.php` | POST | asset-update en check-in |
| `tickets/create.php` | POST | enrollment- en transfertickets |

Create schrijft `asset_name`, `asset_serial`, `asset_make`, `asset_model`,
`asset_os`, `asset_mac`, `asset_ip`, `asset_type` en `asset_status`. Update
schrijft gewijzigde lokale velden, een lege `asset_name`, gewijzigde primaire
MAC/IP en altijd `asset_description` met een check-in in de lokale servertijd,
geformatteerd als `YYYY-MM-DD HH:MM:SS`. Bij create worden zowel `asset_ip` als
de eerste check-in direct meegestuurd. Bij updates wordt de actuele ITFlow-waarde
vergeleken, zodat een ontbrekend IP opnieuw wordt aangeboden zonder een bestaand
IP met een lege detectiewaarde te overschrijven.

De API-key wordt wegens het bestaande ITFlow-contract bij GET als parameter
verstuurd, maar wordt nooit door de agent gelogd. `requests` verzorgt correcte
URL-encoding.

## Installatie

Kloon of kopieer de repository naar een Debian-machine en voer uit:

```sh
sudo sh install.sh
```

De installer:

1. installeert Python, venv, pip, `iproute2` en `util-linux`;
2. installeert de applicatie en virtualenv onder `/opt/itflow-agent`;
3. maakt `/etc/itflow-agent/config.toml` als die nog niet bestaat;
4. maakt een leeg secretbestand `/etc/itflow-agent/api-key` met mode `0600`;
5. installeert en activeert de systemd timer, maar start hem nog niet.

De service draait standaard als `root`, zodat DMI-identiteit ook beschikbaar is
op systemen die `/sys/class/dmi/id/product_serial` voor niet-rootgebruikers
afschermen. De unit behoudt onder meer `NoNewPrivileges=yes`,
`ProtectSystem=strict`, `ProtectHome=yes` en de overige systemd-hardening.

Bewerk daarna:

```sh
sudoedit /etc/itflow-agent/config.toml
sudoedit /etc/itflow-agent/api-key
sudo chmod 600 /etc/itflow-agent/api-key
```

Test eerst niet-muterend met een tijdelijke systemd-unit. De API-key komt
daarbij niet in de commandline of shellgeschiedenis:

```sh
sudo systemd-run --wait --pipe --collect \
  --uid=root --gid=root \
  --property=LoadCredential=itflow_api_key:/etc/itflow-agent/api-key \
  /opt/itflow-agent/venv/bin/itflow-agent \
  --config /etc/itflow-agent/config.toml --test
```

Of test via exact dezelfde systemd-credentialcontext, waarbij de normale
service wel muterend is:

```sh
sudo systemctl start itflow-agent.service
sudo journalctl -u itflow-agent.service -n 100 --no-pager
```

Start vervolgens het schema:

```sh
sudo systemctl enable --now itflow-agent.timer
systemctl list-timers itflow-agent.timer
```

## Configuratie

Voorbeeld: `config/config.toml.example`.

```toml
base_url = "https://itflow.example.com"
client_id = 11
asset_status = "Deployed"
follow_transfers = true
persist_followed_client = false
create_tickets = true
request_timeout_seconds = 30
verify_tls = true
state_dir = "/var/lib/itflow-agent"
```

Geheimen horen niet in TOML. De systemd-unit gebruikt:

```ini
LoadCredential=itflow_api_key:/etc/itflow-agent/api-key
```

De applicatie zoekt de key in deze volgorde:

1. `ITFLOW_API_KEY` (handmatige/CI-uitvoering);
2. de systemd credential `itflow_api_key`;
3. `api_key_file` uit TOML, indien expliciet ingesteld.

Voor sterkere at-rest-bescherming kan de `LoadCredential`-regel door een
beheerder worden vervangen door `LoadCredentialEncrypted` met een credential
die via `systemd-creds encrypt` is gemaakt.

## Matching en transfers

1. De agent leest `/sys/class/dmi/id/product_serial`, waarbij geldige interne
   spaties (zoals in VMware-serials) behouden blijven.
2. Als die waarde ontbreekt of onbruikbaar is, gebruikt de agent een geldige
   `/sys/class/dmi/id/product_uuid` in het hoofdletterformaat van de Windows-agent.
3. Lege, te korte en bekende generieke OEM-serials worden geweigerd; lege,
   ongeldige en volledig nul/`F` UUID's worden eveneens geweigerd.
4. Hij zoekt exact op serial binnen de effectieve client.
5. Bij nul resultaten volgt een globale serialzoekactie.
6. Meer dan één resultaat in een scope is ambigu: exitcode 4, zonder mutaties.
7. Eén globale match kan worden gevolgd als `follow_transfers = true`.
8. Geen enkele match leidt tot enrollment.

`persist_followed_client = false` houdt de beheerde configuratie leidend. Bij
`true` wordt de gevolgde client alleen in `/var/lib/itflow-agent/state.json`
opgeslagen; de TOML-configuratie wordt nooit herschreven.

`/etc/machine-id` wordt bewust niet als automatische serialfallback gebruikt,
omdat die bij images en herinstallaties niet dezelfde hardware-identiteit
garandeert.

## Dry-run

```sh
/opt/itflow-agent/venv/bin/itflow-agent --test
```

Dry-run doet wel inventory, TLS, connectivity en GET-lookups. De modus doet
geen POST, maakt geen tickets en schrijft geen state of snapshot. In logging
staat welke create/update zou plaatsvinden.

## Logging en status

```sh
journalctl -u itflow-agent.service --since today
systemctl status itflow-agent.timer
```

Exitcodes:

| Code | Betekenis |
|---:|---|
| 0 | sync of dry-run geslaagd |
| 1 | onverwachte interne fout |
| 2 | configuratie- of identiteitsfout |
| 3 | netwerk- of ITFlow API-fout |
| 4 | ambigue serialmatch |
| 5 | inventoryfout |

## Tests en ontwikkeling

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest
```

De tests gebruiken geen live ITFlow-instance en muteren het hostsysteem niet.

## Bewuste beperkingen

- Geen hostname-renaming of rebootbeheer.
- Geen Active Directory/LDAP-mutaties.
- Geen displayinventaris; EDID is op headless Linux onbetrouwbaar.
- Geen SMART-health; dat vereist extra tooling en privileges.
- Geen fallback naar MAC of machine-id voor assetidentiteit.
- Geen automatische mutatie van beheerconfiguratie.
