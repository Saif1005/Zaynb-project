#!/bin/bash
# Script pour corriger la clé SSH

set -e

KEY_NAME="saif-pipeline-complet"
KEY_PATH="$HOME/.ssh/$KEY_NAME"

echo "🔧 Correction de la clé SSH: $KEY_NAME"
echo ""

# Supprimer la clé invalide
if [ -f "$KEY_PATH" ]; then
    echo "🗑️  Suppression de la clé invalide..."
    rm -f "$KEY_PATH"
    echo "✅ Clé invalide supprimée"
fi

echo ""
echo "📥 Téléchargez maintenant la clé depuis AWS Console:"
echo ""
echo "1. Ouvrez: https://console.aws.amazon.com/ec2/v2/home?region=eu-west-3#KeyPairs:"
echo "2. Recherchez la paire de clés: $KEY_NAME"
echo "3. Sélectionnez-la et cliquez sur 'Actions' > 'Download private key'"
echo "4. Le fichier sera téléchargé (généralement dans ~/Downloads/)"
echo ""
read -p "Appuyez sur Entrée une fois le téléchargement terminé..."

# Chercher le fichier téléchargé
echo ""
echo "🔍 Recherche du fichier téléchargé..."
DOWNLOADED_KEY=$(find ~/Downloads ~/Desktop -name "*.pem" -type f -newer "$KEY_PATH" 2>/dev/null | head -1)

if [ -z "$DOWNLOADED_KEY" ]; then
    # Chercher aussi dans les chemins Windows (WSL)
    DOWNLOADED_KEY=$(find /mnt/c/Users/*/Downloads -name "*.pem" -type f 2>/dev/null | grep -i "$KEY_NAME" | head -1)
fi

if [ -z "$DOWNLOADED_KEY" ]; then
    # Demander le chemin manuellement
    echo ""
    echo "💡 Astuce: Dans WSL, les chemins Windows sont accessibles via /mnt/c/..."
    echo "   Exemple: /mnt/c/Users/saifa/Downloads/saif-pipeline-complet.pem"
    read -p "Entrez le chemin complet du fichier .pem téléchargé: " downloaded_key
    # Nettoyer les guillemets et backslashes Windows
    downloaded_key=$(echo "$downloaded_key" | sed 's/^"//;s/"$//' | sed 's/\\/\//g' | sed 's/C:/\/mnt\/c/i')
    DOWNLOADED_KEY="$downloaded_key"
fi

if [ -f "$DOWNLOADED_KEY" ]; then
    echo "📋 Copie de la clé..."
    cp "$DOWNLOADED_KEY" "$KEY_PATH"
    chmod 400 "$KEY_PATH"
    echo "✅ Clé copiée dans $KEY_PATH"
    
    # Tester la clé
    echo ""
    echo "🧪 Test de la clé..."
    if ssh-keygen -l -f "$KEY_PATH" > /dev/null 2>&1; then
        echo "✅ Clé valide!"
        echo ""
        ssh-keygen -l -f "$KEY_PATH"
        echo ""
        echo "🧪 Test de connexion à l'instance..."
        if ssh -i "$KEY_PATH" -o StrictHostKeyChecking=no -o ConnectTimeout=5 ec2-user@15.188.127.194 "echo '✅ Connexion SSH réussie!'" 2>/dev/null; then
            echo "✅ Connexion SSH testée avec succès!"
        else
            echo "⚠️  La clé est valide mais la connexion a échoué. Vérifiez:"
            echo "   - Que l'instance est en cours d'exécution"
            echo "   - Que le Security Group autorise SSH (port 22)"
            echo "   - Que l'IP publique est correcte: 15.188.127.194"
        fi
    else
        echo "❌ La clé semble toujours invalide."
        echo "   Vérifiez que vous avez téléchargé le bon fichier depuis AWS."
        exit 1
    fi
else
    echo "❌ Fichier non trouvé: $DOWNLOADED_KEY"
    echo ""
    echo "📝 Instructions manuelles:"
    echo "  1. Téléchargez la clé depuis AWS Console"
    echo "  2. Copiez-la manuellement:"
    echo "     cp /chemin/vers/fichier.pem $KEY_PATH"
    echo "  3. Définissez les permissions:"
    echo "     chmod 400 $KEY_PATH"
    exit 1
fi

