# tiktok-prono

Génère automatiquement des vidéos TikTok « prono du jour » : pour chaque match
du jour, deux équipes s'affrontent dans un mini-jeu physique (course de billes,
évasion d'anneaux, guerre de territoire, combat de balles armées). Le vainqueur
est tiré selon la forme des équipes, puis la simulation est choisie pour que la
physique produise ce résultat.

## Installation (macOS)

```bash
brew install ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # puis renseigner FOOTBALL_DATA_TOKEN
```

Token gratuit : https://www.football-data.org/

## Utilisation

```bash
python main.py --demo                          # matchs fictifs, sans API
python main.py                                 # matchs réels du jour
python main.py --demo --limit 1 --game ball_battle
python test_pipeline.py                        # test complet, étape par étape
```

Jeux disponibles : `ball_race`, `ring_escape`, `color_war`, `ball_battle`
(par défaut, un jeu au hasard par match).

Les vidéos, leurs légendes et un `manifest.json` sont écrits dans `output/<date>/`.

## Police

Pour un rendu plus « TikTok », déposer une police `.ttf` grasse dans
`assets/fonts/` (par exemple Montserrat Black sur Google Fonts). Sinon, une
police système grasse est utilisée (Arial Black sur Mac).

## Automatisation

`.github/workflows/daily.yml` génère les vidéos chaque matin sur GitHub Actions.
Ajouter le secret `FOOTBALL_DATA_TOKEN` dans Settings → Secrets and variables → Actions.
