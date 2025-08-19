# BRVM Technical Analysis

Ce projet automatise le calcul d'indicateurs d'analyse technique (Moyennes Mobiles, Bandes de Bollinger, MACD, RSI, Stochastique) pour les sociétés de la BRVM à partir de données brutes stockées dans un Google Sheet.

## 🚀 Configuration Initiale

Suivez ces étapes pour rendre le projet opérationnel.

### Étape 1 : Créer un Dépôt GitHub

1.  Créez un nouveau dépôt sur GitHub. **Il est fortement recommandé de le rendre `Privé`** pour protéger vos informations.
2.  Ajoutez les deux fichiers suivants à ce dépôt :
    *   `main.py` (le script Python)
    *   `.github/workflows/daily_run.yml` (le fichier d'automatisation)

### Étape 2 : Configurer le Compte de Service Google

1.  **Créez un Compte de Service :**
    *   Allez sur la [page des comptes de service de Google Cloud](https://console.cloud.google.com/iam-admin/serviceaccounts).
    *   Sélectionnez votre projet.
    *   Cliquez sur **"+ CRÉER UN COMPTE DE SERVICE"**.
    *   Donnez-lui un nom (ex: `brvm-analysis-bot`) et cliquez sur **"CRÉER ET CONTINUER"**.
    *   Donnez-lui le rôle **"Éditeur"** (`Editor`) et cliquez sur **"OK"**.

2.  **Générez une Clé JSON :**
    *   Cliquez sur votre nouveau compte de service, allez dans l'onglet **"CLÉS"**, puis **"AJOUTER UNE CLÉ"** -> **"Créer une nouvelle clé"**.
    *   Choisissez le format **JSON** et cliquez sur **"CRÉER"**. Un fichier `.json` sera téléchargé.

3.  **Partagez votre Google Sheet :**
    *   Ouvrez le fichier JSON et copiez l'adresse e-mail de la ligne `"client_email"`.
    *   Allez sur votre [Google Sheet](https://docs.google.com/spreadsheets/d/1EGXyg13ml8a9zr4OaUPnJN3i-rwVO2uq330yfxJXnSM/edit).
    *   Cliquez sur **"Partager"**, collez l'adresse e-mail, donnez-lui les droits **"Éditeur"**, et envoyez.

### Étape 3 : Ajouter la Clé JSON aux Secrets GitHub

1.  Dans votre dépôt GitHub, allez dans **`Settings`** -> **`Secrets and variables`** -> **`Actions`**.
2.  Cliquez sur **`New repository secret`**.
3.  **Name:** `GSPREAD_SERVICE_ACCOUNT`
4.  **Value:** Collez l'intégralité du contenu de votre fichier `.json`.
5.  Cliquez sur **`Add secret`**.

### Étape 4 : Activer et Tester le Workflow

1.  Allez dans l'onglet **`Actions`** de votre dépôt GitHub.
2.  Cliquez sur "BRVM Technical Analysis Daily Run" à gauche.
3.  Cliquez sur le bouton **`Run workflow`** pour lancer un test manuel.

Le script tournera désormais automatiquement tous les jours à 07h00 UTC.
