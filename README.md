# Scanner d'Identité - Éditeur PDF interactif

Application de numérisation, édition et assemblage de documents d'identité (recto/verso) avec système de calques, filigrane personnalisable, export PDF et impression directe.

## Fonctionnalités

- **Numérisation** : détection automatique des scanners (via `scanimage`), sélection de la source (vitre, chargeur automatique).
- **Édition par calques** : chaque image scannée ou importée est un calque déplaçable sur l'aperçu A4.
- **Filigrane** : texte ou image, avec réglage de la police, taille, angle, couleur, opacité. Possibilité d'ajouter plusieurs filigranes.
- **Réglages d'image** : luminosité et contraste appliqués en temps réel.
- **Export PDF** : génération d'une page A4 (2480x3508 px, 300 DPI) avec tous les calques.
- **Impression directe** : envoi à l'imprimante par défaut (Linux/Windows).
- **Thèmes** : interface « Pure Flat » avec thème clair moderne (par défaut).

## Installation

### Dépendances

- Python 3.6+
- `Pillow` (PIL)
- `tkinter` (intégré à Python)
- `scanimage` (pour la numérisation, généralement fourni avec `sane-utils`)

```bash
pip install Pillow
