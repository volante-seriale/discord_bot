# Discord Leveling & Utility Bot

Un bot Discord multifunzione con sistema di **livellamento XP**, **canali vocali temporanei**, **moderazione base**, **kick automatico per utenti senza ruolo** e comandi utili per gli amministratori.

## Funzionalità principali

### Sistema di Livellamento (Leveling)
- Guadagno di 1 XP per ogni messaggio inviato (non comandi)
- 5 livelli configurabili con soglia XP crescente
- Assegnazione automatica di ruoli al raggiungimento di un livello
- Rimozione del ruolo precedente al level-up
- Messaggio di congratulazioni nel canale configurato
- Comando `/level` per vedere il proprio livello e progresso (con barra progresso)
- Comando `/config` per impostare ruoli, canale level-up e link invito
- Possibilità di disattivare il sistema per server (`/leveling-toggle`)

### Canali Vocali Temporanei (TempVoice)
- Un canale "creatore" configurabile
- Quando un utente entra nel canale creatore → viene creato un canale vocale personale con il suo nome
- L'utente diventa automaticamente gestore del canale
- Il canale viene eliminato automaticamente quando resta vuoto

### Moderazione & Utility
- Messaggio di addio configurabile quando un membro lascia il server
- Kick automatico dopo 48 ore per chi non ha nessun ruolo (escluso @everyone)
  - Task in background ogni 60 minuti
  - Disattivabile per server con `/bg-task-toggle`
- `/list-id @ruolo` → scarica un file .txt con ID e nome di tutti i membri con quel ruolo
- `/serverinfo` → informazioni base del server + link invito (se configurato)
- `/ping` → latency del bot
- `/sync` → sincronizzazione globale dei comandi slash (solo owner)

## Comandi Principali

| Comando               | Descrizione                                           | Permessi richiesti         |
|-----------------------|-------------------------------------------------------|----------------------------|
| `/ping`               | Mostra la latenza del bot                             | Tutti                      |
| `/serverinfo`         | Info del server + link invito                         | Tutti                      |
| `/level` [membro]     | Mostra livello e XP (proprio o di un altro utente)    | Tutti                      |
| `/list-id @ruolo`     | Scarica lista ID + nome dei membri con quel ruolo     | Amministratore             |
| `/config`             | Configura tutto (canali, ruoli, link, ecc.)           | Amministratore             |
| `/config-show`        | Visualizza la configurazione attuale                  | Amministratore             |
| `/leveling-toggle`    | Attiva/disattiva il sistema di livellamento           | Amministratore             |
| `/bg-task-toggle`     | Attiva/disattiva il kick automatico dopo 48h          | Amministratore             |
| `/sync`               | Sincronizza i comandi slash (globale)                 | Solo Owner del bot         |

## Requisiti

- Python 3.11+
- `discord.py>=2.3.0`
- `python-dotenv`

## Installazione

1. Clona la repository
```bash
git clone https://github.com/tuo-username/nome-bot.git
cd nome-bot
```
2. Crea il file `.env` nella root del progetto
```env
BOT_TOKEN=il_tuo_token_del_bot
BOT_OWNER_ID=il_tuo_user_id
```
3. Avvia il bot
```bash
python bot.py
```
## Struttura dei file
.
├── bot.py                    → File principale del bot
├── cogs/
│   ├── leveling.py           → Sistema XP, comandi config e level-up
│   ├── tempvoice.py          → Canali vocali temporanei
│   ├── moderation.py         → Messaggi di uscita
│   └── member_id.py          → Comando /list-id
├── data/                     → (creata automaticamente)
│   ├── levels.json           → Dati XP e livelli per server/utente
│   ├── config.json           → Configurazione leveling per server
│   ├── moderation_config.json → Canale di uscita membri
│   └── tempvoice_config.json → Canale creatore voce temporanea
├── .env                      → Token e Owner ID (non commitare!)
└── README.md