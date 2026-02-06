#!/bin/bash
# Script pour configurer la clé SSH

set -e

KEY_NAME="${1:-saif-pipeline-complet}"
KEY_PATH="$HOME/.ssh/$KEY_NAME"

echo "🔑 Configuration de la clé SSH: $KEY_NAME"
echo ""

# Vérifier si la clé existe déjà
if [ -f "$KEY_PATH" ]; then
    echo "⚠️  La clé existe déjà: $KEY_PATH"
    read -p "Voulez-vous la remplacer? [y/N]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Annulé."
        exit 0
    fi
    rm -f "$KEY_PATH"
fi

echo "📥 Téléchargement de la clé depuis AWS..."
echo ""
echo "Option 1: Télécharger depuis AWS Console"
echo "  1. Allez sur: https://console.aws.amazon.com/ec2/v2/home?region=eu-west-3#KeyPairs:"
echo "  2. Trouvez la paire de clés: $KEY_NAME"
echo "  3. Cliquez sur 'Actions' > 'Download private key'"
echo "  4. Sauvegardez le fichier .pem"
echo ""
echo "Option 2: Si vous avez déjà le fichier .pem localement"
read -p "Chemin vers le fichier .pem (ou appuyez sur Entrée pour ignorer): " pem_file

if [ -n "$pem_file" ] && [ -f "$pem_file" ]; then
    echo "📋 Copie de la clé..."
    cp "$pem_file" "$KEY_PATH"
    chmod 400 "$KEY_PATH"
    echo "✅ Clé copiée dans $KEY_PATH"
    
    # Tester la clé
    echo ""
    echo "🧪 Test de la clé..."
    if ssh-keygen -l -f "$KEY_PATH" > /dev/null 2>&1; then
        echo "✅ Clé valide!"
        ssh-keygen -l -f "$KEY_PATH"
    else
        echo "❌ La clé semble invalide. Vérifiez le fichier source."
        exit 1
    fi
else
    echo ""
    echo "📝 Instructions manuelles:"
    echo "  1. Téléchargez la clé depuis AWS Console"
    echo "  2. Copiez-la dans: $KEY_PATH"
    echo "  3. Définissez les permissions: chmod 400 $KEY_PATH"
    echo ""
    echo "Ou exécutez ce script avec le chemin du fichier .pem:"
    echo "  bash $0 $KEY_NAME /chemin/vers/votre-cle.pem"
fi




