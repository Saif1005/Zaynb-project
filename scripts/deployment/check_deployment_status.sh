#!/bin/bash
# Script pour vérifier l'état du déploiement

echo "🔍 Vérification de l'état du déploiement..."
echo ""

# Vérifier la connexion ECR
echo "1. Test de connexion ECR..."
if aws ecr get-login-password --region eu-west-3 > /dev/null 2>&1; then
    echo "   ✅ ECR accessible"
else
    echo "   ❌ Problème de connexion ECR"
fi

# Vérifier les repositories ECR
echo ""
echo "2. Vérification des repositories ECR..."
aws ecr describe-repositories --region eu-west-3 --query 'repositories[*].repositoryName' --output table 2>/dev/null || echo "   ⚠️  Impossible de lister les repositories"

# Vérifier les images Docker locales
echo ""
echo "3. Images Docker locales:"
docker images | grep genomic | head -5 || echo "   Aucune image genomic trouvée localement"

# Vérifier les processus Docker
echo ""
echo "4. Processus Docker actifs:"
ps aux | grep -E "docker build|docker push" | grep -v grep || echo "   Aucun build/push en cours"

# Vérifier la connexion SSH
echo ""
echo "5. Test de connexion SSH à l'instance:"
if ssh -i ~/.ssh/saif-pipeline-complet -o ConnectTimeout=5 -o StrictHostKeyChecking=no ubuntu@15.188.127.194 "echo 'OK'" > /dev/null 2>&1; then
    echo "   ✅ Connexion SSH OK"
else
    echo "   ❌ Problème de connexion SSH"
fi

echo ""
echo "💡 Si le build Docker est bloqué, vous pouvez:"
echo "   1. Vérifier les logs: docker logs (si un conteneur tourne)"
echo "   2. Vérifier l'espace disque: df -h"
echo "   3. Relancer le script si nécessaire"




