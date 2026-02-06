#!/bin/bash
# Script pour initialiser le dépôt Git et préparer l'upload sur GitHub

set -e

echo "=========================================="
echo "🚀 Configuration Git pour GitHub"
echo "=========================================="
echo ""

# Vérifier si Git est installé
if ! command -v git &> /dev/null; then
    echo "❌ Git n'est pas installé. Installez Git d'abord."
    exit 1
fi

# Aller dans le répertoire du projet
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "📁 Répertoire du projet: $PROJECT_DIR"
echo ""

# Vérifier si Git est déjà initialisé
if [ -d ".git" ]; then
    echo "⚠️  Git est déjà initialisé dans ce répertoire."
    read -p "Voulez-vous continuer quand même? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    # Initialiser Git
    echo "📦 Initialisation du dépôt Git..."
    git init
    echo "✅ Dépôt Git initialisé"
fi

# Vérifier la configuration Git
echo ""
echo "🔍 Vérification de la configuration Git..."
if [ -z "$(git config user.name)" ]; then
    echo "⚠️  Nom d'utilisateur Git non configuré"
    read -p "Entrez votre nom (pour les commits): " git_name
    git config user.name "$git_name"
fi

if [ -z "$(git config user.email)" ]; then
    echo "⚠️  Email Git non configuré"
    read -p "Entrez votre email (pour les commits): " git_email
    git config user.email "$git_email"
fi

echo "✅ Configuration Git:"
echo "   Nom: $(git config user.name)"
echo "   Email: $(git config user.email)"
echo ""

# Vérifier les fichiers sensibles
echo "🔒 Vérification des fichiers sensibles..."
SENSITIVE_FILES=(
    ".env"
    "*.pem"
    "*.key"
    "id_rsa*"
)

FOUND_SENSITIVE=false
for pattern in "${SENSITIVE_FILES[@]}"; do
    if find . -name "$pattern" -not -path "./.git/*" -not -path "./genomic-env/*" | grep -q .; then
        echo "⚠️  Fichiers sensibles trouvés correspondant à: $pattern"
        find . -name "$pattern" -not -path "./.git/*" -not -path "./genomic-env/*"
        FOUND_SENSITIVE=true
    fi
done

if [ "$FOUND_SENSITIVE" = true ]; then
    echo ""
    echo "⚠️  ATTENTION: Des fichiers sensibles ont été trouvés!"
    echo "   Assurez-vous qu'ils sont bien dans .gitignore"
    read -p "Continuer quand même? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✅ Aucun fichier sensible trouvé (ou bien exclus par .gitignore)"
fi

# Afficher le statut Git
echo ""
echo "📊 Statut Git actuel:"
git status --short | head -20
if [ $(git status --short | wc -l) -gt 20 ]; then
    echo "... (et $(($(git status --short | wc -l) - 20)) autres fichiers)"
fi
echo ""

# Demander si on veut ajouter tous les fichiers
read -p "Voulez-vous ajouter tous les fichiers au staging? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📝 Ajout des fichiers..."
    git add .
    echo "✅ Fichiers ajoutés"
    echo ""
    
    # Afficher ce qui sera commité
    echo "📋 Fichiers qui seront commités:"
    git status --short | head -30
    echo ""
    
    # Demander le message de commit
    read -p "Message de commit (ou Entrée pour message par défaut): " commit_msg
    if [ -z "$commit_msg" ]; then
        commit_msg="Initial commit: Genomic Cancer Detection Pipeline - Agentic AI

- Pipeline complet FASTQ → VCF avec BWA-MEM et GATK HaplotypeCaller
- Système agentic AI avec 6 agents spécialisés
- Fine-tuning LLM (Mistral) pour détection cancer
- Infrastructure AWS (EC2, S3, ECS, Step Functions)
- Documentation complète avec références scientifiques"
    fi
    
    # Créer le commit
    echo ""
    echo "💾 Création du commit..."
    git commit -m "$commit_msg"
    echo "✅ Commit créé"
else
    echo "⏭️  Ajout des fichiers ignoré"
fi

# Vérifier si un remote existe déjà
echo ""
if git remote | grep -q "^origin$"; then
    echo "🔗 Remote 'origin' existe déjà:"
    git remote -v
    echo ""
    read -p "Voulez-vous changer l'URL du remote? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "URL du dépôt GitHub (ex: https://github.com/USERNAME/projet_zaynb.git): " repo_url
        git remote set-url origin "$repo_url"
        echo "✅ Remote mis à jour"
    fi
else
    echo "🔗 Aucun remote configuré"
    read -p "Voulez-vous ajouter un remote GitHub maintenant? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "URL du dépôt GitHub (ex: https://github.com/USERNAME/projet_zaynb.git): " repo_url
        git remote add origin "$repo_url"
        echo "✅ Remote ajouté"
    fi
fi

# Résumé final
echo ""
echo "=========================================="
echo "✅ Configuration terminée!"
echo "=========================================="
echo ""
echo "📝 Prochaines étapes:"
echo ""
echo "1. Créez le dépôt sur GitHub (si pas déjà fait):"
echo "   https://github.com/new"
echo ""
echo "2. Si vous n'avez pas encore ajouté le remote:"
echo "   git remote add origin https://github.com/USERNAME/projet_zaynb.git"
echo ""
echo "3. Renommez la branche en 'main' (si nécessaire):"
echo "   git branch -M main"
echo ""
echo "4. Push vers GitHub:"
echo "   git push -u origin main"
echo ""
echo "📚 Pour plus de détails, consultez: GUIDE_GITHUB_UPLOAD.md"
echo ""
