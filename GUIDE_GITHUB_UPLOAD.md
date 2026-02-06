# Guide pour uploader le projet sur GitHub

Ce guide vous explique étape par étape comment uploader votre projet sur GitHub.

## 📋 Prérequis

1. **Compte GitHub** : Créez un compte sur [github.com](https://github.com) si vous n'en avez pas
2. **Git installé** : Vérifiez avec `git --version`
3. **GitHub CLI (optionnel)** : Pour faciliter l'authentification

---

## 🔐 Étape 1 : Vérifier les fichiers sensibles

Avant d'uploader, assurez-vous que les fichiers sensibles sont bien exclus :

✅ **Fichiers déjà exclus par `.gitignore`** :
- `.env` (variables d'environnement avec secrets AWS)
- `*.pem`, `*.key` (clés SSH/AWS)
- `data/patients/`, `data/training/` (données patients)
- `*.fastq.gz`, `*.bam`, `*.vcf.gz` (fichiers génomiques)
- `.terraform/`, `*.tfstate` (état Terraform)
- `*.log` (logs)

⚠️ **Vérifiez manuellement** :
```bash
# Vérifier qu'il n'y a pas de fichiers sensibles
ls -la | grep -E "\.env|\.pem|\.key"
```

---

## 🚀 Étape 2 : Initialiser le dépôt Git

```bash
# Aller dans le répertoire du projet
cd /mnt/c/Users/saifa/projet_zaynb

# Initialiser Git
git init

# Configurer votre identité Git (si pas déjà fait)
git config --global user.name "Votre Nom"
git config --global user.email "votre.email@example.com"
```

---

## 📝 Étape 3 : Ajouter les fichiers et faire le premier commit

```bash
# Vérifier les fichiers qui seront ajoutés
git status

# Ajouter tous les fichiers (respecte .gitignore)
git add .

# Vérifier ce qui sera commité
git status

# Créer le commit initial
git commit -m "Initial commit: Genomic Cancer Detection Pipeline - Agentic AI

- Pipeline complet FASTQ → VCF avec BWA-MEM et GATK HaplotypeCaller
- Système agentic AI avec 6 agents spécialisés
- Fine-tuning LLM (Mistral) pour détection cancer
- Infrastructure AWS (EC2, S3, ECS, Step Functions)
- Documentation complète avec références scientifiques"
```

---

## 🌐 Étape 4 : Créer le dépôt sur GitHub

### Option A : Via l'interface web GitHub

1. **Aller sur GitHub** : [github.com/new](https://github.com/new)
2. **Remplir les informations** :
   - Repository name : `projet_zaynb` (ou autre nom)
   - Description : `Genomic Cancer Detection Pipeline using Agentic AI`
   - Visibilité : **Public** ou **Private** (recommandé : Private pour données sensibles)
   - **NE PAS** cocher "Initialize with README" (vous avez déjà un README)
3. **Cliquer sur "Create repository"**

### Option B : Via GitHub CLI (si installé)

```bash
# Installer GitHub CLI si pas déjà fait
# Windows: winget install GitHub.cli
# Linux: sudo apt install gh
# Mac: brew install gh

# Se connecter à GitHub
gh auth login

# Créer le dépôt (private par défaut)
gh repo create projet_zaynb --private --source=. --remote=origin --push
```

---

## 🔗 Étape 5 : Lier le dépôt local à GitHub

### Si vous avez créé le dépôt via l'interface web :

```bash
# Ajouter le remote GitHub (remplacez USERNAME par votre nom d'utilisateur)
git remote add origin https://github.com/USERNAME/projet_zaynb.git

# Ou avec SSH (si vous avez configuré une clé SSH)
git remote add origin git@github.com:USERNAME/projet_zaynb.git

# Vérifier le remote
git remote -v
```

### Si vous avez utilisé GitHub CLI :

Le remote est déjà configuré, passez à l'étape 6.

---

## 📤 Étape 6 : Push vers GitHub

```bash
# Renommer la branche principale en 'main' (standard GitHub)
git branch -M main

# Push vers GitHub
git push -u origin main
```

**Si vous avez des erreurs d'authentification** :

### Option 1 : Token d'accès personnel (HTTPS)

1. **Créer un token** : [github.com/settings/tokens](https://github.com/settings/tokens)
   - Cliquez sur "Generate new token (classic)"
   - Sélectionnez les scopes : `repo` (accès complet aux dépôts)
   - Copiez le token généré

2. **Utiliser le token** :
```bash
# Quand Git demande le mot de passe, utilisez le token
git push -u origin main
# Username: votre_username
# Password: votre_token
```

### Option 2 : Clé SSH (recommandé)

1. **Générer une clé SSH** (si pas déjà fait) :
```bash
ssh-keygen -t ed25519 -C "votre.email@example.com"
# Appuyez sur Entrée pour accepter le chemin par défaut
# Entrez une passphrase (optionnel mais recommandé)
```

2. **Ajouter la clé à GitHub** :
```bash
# Copier la clé publique
cat ~/.ssh/id_ed25519.pub
# Ou sur Windows: type %USERPROFILE%\.ssh\id_ed25519.pub
```

3. **Sur GitHub** :
   - Allez dans Settings → SSH and GPG keys
   - Cliquez sur "New SSH key"
   - Collez la clé publique
   - Sauvegardez

4. **Utiliser SSH** :
```bash
# Changer le remote en SSH
git remote set-url origin git@github.com:USERNAME/projet_zaynb.git

# Push
git push -u origin main
```

---

## ✅ Étape 7 : Vérifier sur GitHub

1. **Allez sur votre dépôt** : `https://github.com/USERNAME/projet_zaynb`
2. **Vérifiez** :
   - ✅ Tous les fichiers sont présents
   - ✅ Le README.md s'affiche correctement
   - ✅ Les fichiers sensibles (.env, *.pem) ne sont **PAS** visibles
   - ✅ La structure du projet est correcte

---

## 🔒 Sécurité : Vérifications finales

### Vérifier qu'aucun secret n'a été commité :

```bash
# Chercher des patterns de secrets dans l'historique Git
git log --all --full-history --source -- "*" | grep -i "password\|secret\|key\|token" | head -20

# Chercher dans les fichiers actuels
grep -r "AKIA" . --exclude-dir=.git --exclude-dir=genomic-env  # AWS Access Key
grep -r "sk-" . --exclude-dir=.git --exclude-dir=genomic-env  # Clés API
```

### Si vous avez accidentellement commité un secret :

```bash
# Supprimer un fichier de l'historique Git (ATTENTION : destructif)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# Force push (ATTENTION : cela réécrit l'historique)
git push origin --force --all
```

**⚠️ Important** : Si vous avez déjà pushé des secrets, **changez-les immédiatement** sur AWS/GitHub/etc.

---

## 📚 Étape 8 : Améliorer le dépôt (optionnel)

### Ajouter une licence

```bash
# Créer un fichier LICENSE (MIT recommandé)
# Ou utiliser GitHub pour générer une licence
```

### Ajouter des badges au README

Ajoutez en haut du README.md :

```markdown
![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![AWS](https://img.shields.io/badge/AWS-EC2%2CS3%2CECS-orange.svg)
```

### Créer un fichier CONTRIBUTING.md

Pour guider les contributeurs.

---

## 🎯 Commandes rapides de référence

```bash
# Vérifier le statut
git status

# Ajouter des fichiers
git add .

# Commit
git commit -m "Description du changement"

# Push
git push origin main

# Voir l'historique
git log --oneline

# Voir les différences
git diff
```

---

## 🆘 Dépannage

### Erreur : "remote origin already exists"
```bash
git remote remove origin
git remote add origin https://github.com/USERNAME/projet_zaynb.git
```

### Erreur : "failed to push some refs"
```bash
# Récupérer les changements distants d'abord
git pull origin main --allow-unrelated-histories
# Résoudre les conflits si nécessaire
git push -u origin main
```

### Erreur : "authentication failed"
- Vérifiez votre token/clé SSH
- Utilisez GitHub CLI : `gh auth login`

---

## 📞 Support

Si vous rencontrez des problèmes :
1. Consultez la [documentation GitHub](https://docs.github.com)
2. Vérifiez que `.gitignore` exclut bien les fichiers sensibles
3. Utilisez `git status` pour voir ce qui sera commité

---

**🎉 Félicitations ! Votre projet est maintenant sur GitHub !**
