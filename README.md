# 🎮 Gaming Hub

Gaming Hub is a real-time platform where users can create rooms and collaborate with others in one shared space.

It is designed for interaction, teamwork, and social gaming experiences — all in one place.

---

## 🌍 Live Demo
👉 https://gaminghubcompany.pythonanywhere.com/

---

## ✨ Key Features

- 🏠 Create and join rooms instantly  
- 👥 Collaborate with other users in real time  
- 💬 Communicate and interact inside rooms  
- 🎮 Play and engage together in shared spaces  
- ⚡ Simple and fast interface  

---

## 🛠️ Built With

- HTML  
- CSS  
- JavaScript  
- Python (Backend / Flask)

---

## 🚀 How It Works

1. Create a room or join an existing one  
2. Share the room code/link with others  
3. Collaborate and interact in real time  

---

## 💡 Project Vision

The goal of Gaming Hub is to make online collaboration more interactive and fun by combining gaming-style rooms with real-time user interaction.

---

## 📸 Preview



---

## 🚀 Deployment

Hosted on PythonAnywhere

---

## 👤 Author

**Al-ameen Olanrewaju**

---

## ⭐ Support

If you find this project useful, consider giving it a ⭐ and sharing it with others.

## Run Gaming Hub

Gaming Hub runs on Flask and uses the existing `db.sqlite3` database and media
files.

Install the project dependencies and run the Flask development server with:

```powershell
pip install -r requirements.txt
python manage.py
```

For WSGI deployments, the application is exposed as `app:app` in `app.py`;
the existing `gaming_hub.wsgi:application` path also points to Flask. Set
`SECRET_KEY` (or `FLASK_SECRET_KEY`) in the environment or in the project's
local `.env` file before deploying. To enable welcome, contact, and
password-reset emails, configure `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`,
`MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`, and `MAIL_USE_TLS` (or `MAIL_USE_SSL`).
Set `ADMIN_EMAIL` to receive security notifications when users sign in.
Password reset links also require `PUBLIC_BASE_URL` to be set to the canonical
HTTPS site URL. Set `FLASK_COOKIE_SECURE=true` when serving the app over HTTPS.
Never commit real credentials to source control.

## Play Gaming Hub Originals

Create a room and select one of the Gaming Hub Originals. Invite at least one
other player, then the host starts the round from the room page or game lobby.
Neon Sprint is a boost race; Cipher Clash is a ten-guess four-digit codebreaker;
Tactic Grid is a two-player Connect Four match; Reaction Relay is a reaction
test with random signals and penalties for false starts. Players use the game
page to compete together; room state and scores refresh through the Flask server.
Reaction Relay checks for signals ten times per second.
Completed matches are saved separately from active room state and appear on the
overall Originals leaderboard and each game's leaderboard; draws count as
matches but do not award wins.
The game runtime uses a separate SQLite file at
`instance/live_games.sqlite3` by default. Set
`GAMING_HUB_GAME_DATABASE` to a persistent writable path for deployments.
These are original browser mini-games, not playable versions of the external
commercial games in the catalog.

The tournament payment flow records submissions as pending for a staff member
to review; it does not charge or verify payments automatically. Clash Royale
uses demo data unless a valid `CLASH_ROYALE_API_KEY` is configured and live
mode is enabled.
