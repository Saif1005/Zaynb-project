#!/bin/bash
# Script pour déployer l'application sur l'instance EC2

set -e

# Couleurs pour les messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Variables
INSTANCE_IP="${INSTANCE_IP:-15.188.127.194}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/saif-pipeline-complet}"
SSH_USER="${SSH_USER:-ubuntu}"
AWS_REGION="${AWS_REGION:-eu-west-3}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-622994489865}"
PROJECT_DIR="/mnt/c/Users/saifa/projet_zaynb"

# Expanser le tilde dans SSH_KEY si présent
SSH_KEY="${SSH_KEY/#\~/$HOME}"

echo -e "${BLUE}🚀 Déploiement sur l'instance EC2${NC}"
echo -e "${BLUE}Instance IP: $INSTANCE_IP${NC}"
echo -e "${BLUE}Région AWS: $AWS_REGION${NC}"

# Vérifier que nous sommes dans le bon répertoire
if [ ! -f "$PROJECT_DIR/requirements.txt" ]; then
    echo -e "${RED}Erreur: requirements.txt non trouvé. Assurez-vous d'être dans le répertoire du projet.${NC}"
    exit 1
fi

# Fonction pour exécuter des commandes sur l'instance
run_remote() {
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$INSTANCE_IP" "$@"
}

# Fonction pour copier des fichiers
copy_to_remote() {
    scp -i "$SSH_KEY" -o StrictHostKeyChecking=no -r "$1" "$SSH_USER@$INSTANCE_IP:$2"
}

echo -e "${YELLOW}📦 Étape 1: Build des images Docker...${NC}"
cd "$PROJECT_DIR"

# Créer les repositories ECR s'ils n'existent pas
echo -e "${YELLOW}📦 Création des repositories ECR...${NC}"
aws ecr create-repository --repository-name genomic-api --region $AWS_REGION 2>/dev/null || echo "Repository genomic-api existe déjà"
aws ecr create-repository --repository-name genomic-agent --region $AWS_REGION 2>/dev/null || echo "Repository genomic-agent existe déjà"

# Vérifier si Docker est disponible localement
if command -v docker &> /dev/null && docker info &> /dev/null; then
    echo -e "${GREEN}✅ Docker disponible localement, build local...${NC}"
    
    # Login à ECR
    echo -e "${YELLOW}🔐 Connexion à ECR...${NC}"
    aws ecr get-login-password --region $AWS_REGION | \
        docker login --username AWS --password-stdin \
        ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
    
    # Build les images
    echo -e "${YELLOW}🔨 Build de l'image API...${NC}"
    docker build -f docker/Dockerfile.api -t genomic-api:latest .
    
    echo -e "${YELLOW}🔨 Build de l'image Agent...${NC}"
    docker build -f docker/Dockerfile.agent -t genomic-agent:latest .
    
    # Tag et push
    echo -e "${YELLOW}📤 Push des images vers ECR...${NC}"
    API_IMAGE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/genomic-api:latest"
    AGENT_IMAGE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/genomic-agent:latest"
    
    docker tag genomic-api:latest $API_IMAGE
    docker tag genomic-agent:latest $AGENT_IMAGE
    
    docker push $API_IMAGE
    docker push $AGENT_IMAGE
    
    echo -e "${GREEN}✅ Images pushées vers ECR${NC}"
else
    echo -e "${YELLOW}⚠️  Docker non disponible localement, build sur l'instance EC2...${NC}"
    
    # Copier le code d'abord (nécessaire pour le build)
    echo -e "${YELLOW}📁 Copie du code source pour le build...${NC}"
    tar --exclude='.git' \
        --exclude='genomic-env' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache' \
        --exclude='terraform/.terraform' \
        --exclude='terraform/*.tfstate*' \
        -czf /tmp/genomic-pipeline.tar.gz \
        -C "$PROJECT_DIR" .
    
    copy_to_remote "/tmp/genomic-pipeline.tar.gz" "~/genomic-pipeline.tar.gz"
    run_remote "cd ~ && rm -rf genomic-pipeline && mkdir -p genomic-pipeline && tar -xzf genomic-pipeline.tar.gz -C genomic-pipeline/ && rm genomic-pipeline.tar.gz"
    
    # Build sur l'instance EC2
    echo -e "${YELLOW}🔐 Connexion à ECR depuis l'instance...${NC}"
    ECR_LOGIN=$(aws ecr get-login-password --region $AWS_REGION)
    run_remote "echo '$ECR_LOGIN' | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
    
    echo -e "${YELLOW}🔨 Build de l'image API sur l'instance...${NC}"
    run_remote "cd ~/genomic-pipeline && docker build -f docker/Dockerfile.api -t genomic-api:latest ."
    
    echo -e "${YELLOW}🔨 Build de l'image Agent sur l'instance...${NC}"
    run_remote "cd ~/genomic-pipeline && docker build -f docker/Dockerfile.agent -t genomic-agent:latest ."
    
    # Tag et push depuis l'instance
    echo -e "${YELLOW}📤 Push des images vers ECR depuis l'instance...${NC}"
    API_IMAGE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/genomic-api:latest"
    AGENT_IMAGE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/genomic-agent:latest"
    
    run_remote "docker tag genomic-api:latest $API_IMAGE"
    run_remote "docker tag genomic-agent:latest $AGENT_IMAGE"
    
    run_remote "docker push $API_IMAGE"
    run_remote "docker push $AGENT_IMAGE"
    
    echo -e "${GREEN}✅ Images pushées vers ECR${NC}"
fi

echo -e "${YELLOW}📁 Étape 2: Copie du code source sur l'instance...${NC}"
# Si le code n'a pas déjà été copié (build sur EC2), le copier maintenant
if ! run_remote "test -d ~/genomic-pipeline" >/dev/null 2>&1; then
    # Créer un archive du code source (sans les fichiers inutiles)
    tar --exclude='.git' \
        --exclude='genomic-env' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache' \
        --exclude='terraform/.terraform' \
        --exclude='terraform/*.tfstate*' \
        -czf /tmp/genomic-pipeline.tar.gz \
        -C "$PROJECT_DIR" .
    
    # Copier l'archive
    copy_to_remote "/tmp/genomic-pipeline.tar.gz" "~/genomic-pipeline.tar.gz"
    
    # Extraire sur l'instance
    run_remote "cd ~ && mkdir -p genomic-pipeline && tar -xzf genomic-pipeline.tar.gz -C genomic-pipeline/ && rm genomic-pipeline.tar.gz"
else
    echo -e "${GREEN}✅ Code source déjà présent sur l'instance${NC}"
fi

echo -e "${YELLOW}🐍 Étape 3: Installation de l'environnement Python...${NC}"
run_remote "cd ~/genomic-pipeline && python3 -m venv venv"
run_remote "cd ~/genomic-pipeline && source venv/bin/activate && pip install --upgrade pip"
run_remote "cd ~/genomic-pipeline && source venv/bin/activate && pip install -r requirements.txt"

echo -e "${YELLOW}⚙️  Étape 4: Configuration des variables d'environnement...${NC}"
# Créer un fichier .env sur l'instance
run_remote "cat > ~/genomic-pipeline/.env <<EOF
AWS_REGION=$AWS_REGION
AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID
INSTANCE_ID=i-00394cd5fb3224ca5
USE_AWS=true
EOF"

echo -e "${YELLOW}🔧 Étape 5: Configuration d'AWS CLI sur l'instance...${NC}"
echo -e "${YELLOW}⚠️  Note: L'instance doit avoir un rôle IAM avec les permissions appropriées${NC}"

echo -e "${GREEN}✅ Déploiement terminé!${NC}"
echo -e "${BLUE}📝 Prochaines étapes:${NC}"
echo -e "1. Vérifier que l'instance a le rôle IAM 'EC2-GPU-LLM-Role'"
echo -e "2. Tester la connexion: ssh -i $SSH_KEY $SSH_USER@$INSTANCE_IP"
echo -e "3. Lancer l'API: cd ~/genomic-pipeline && source venv/bin/activate && python scripts/api/start_api_aws.py"

