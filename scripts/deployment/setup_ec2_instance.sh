#!/bin/bash
# Script pour configurer l'instance EC2 avec toutes les dépendances nécessaires

set -e

# Couleurs pour les messages
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Variables (à définir avant d'exécuter)
INSTANCE_IP="${INSTANCE_IP:-}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/saif-pipeline-complet}"
SSH_USER="${SSH_USER:-ubuntu}"

# Expanser le tilde dans SSH_KEY si présent
SSH_KEY="${SSH_KEY/#\~/$HOME}"

if [ -z "$INSTANCE_IP" ]; then
    echo -e "${RED}Erreur: INSTANCE_IP n'est pas défini${NC}"
    echo "Usage: INSTANCE_IP=15.188.127.194 SSH_KEY=~/.ssh/saif-pipeline-complet bash setup_ec2_instance.sh"
    exit 1
fi

echo -e "${GREEN}🚀 Configuration de l'instance EC2: $INSTANCE_IP${NC}"

# Fonction pour exécuter des commandes sur l'instance
run_remote() {
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "$SSH_USER@$INSTANCE_IP" "$@"
}

# Fonction pour copier des fichiers
copy_to_remote() {
    scp -i "$SSH_KEY" -o StrictHostKeyChecking=no "$1" "$SSH_USER@$INSTANCE_IP:$2"
}

echo -e "${YELLOW}📦 Mise à jour du système...${NC}"
run_remote "sudo apt-get update -y"

echo -e "${YELLOW}🐳 Installation de Docker...${NC}"
run_remote "sudo apt-get install -y docker.io docker-compose"
run_remote "sudo systemctl start docker"
run_remote "sudo systemctl enable docker"
run_remote "sudo usermod -aG docker $SSH_USER"

echo -e "${YELLOW}🐍 Installation de Python 3.12...${NC}"
# Ubuntu 24.04 a déjà Python 3.12, on installe pip et les outils de développement
run_remote "sudo apt-get install -y python3 python3-pip python3-venv python3-full python3-dev gcc build-essential"
run_remote "python3 --version"
# Mettre à jour pip dans un environnement virtuel temporaire ou utiliser --break-system-packages
run_remote "python3 -m pip install --upgrade pip --break-system-packages || python3 -m pip install --user --upgrade pip"

echo -e "${YELLOW}📚 Installation des dépendances système...${NC}"
run_remote "sudo apt-get install -y git curl wget unzip jq"

echo -e "${YELLOW}☁️ Installation d'AWS CLI...${NC}"
run_remote "curl 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o /tmp/awscliv2.zip"
run_remote "sudo apt-get install -y unzip"
run_remote "rm -rf /tmp/aws && unzip -q -o /tmp/awscliv2.zip -d /tmp"
run_remote "sudo /tmp/aws/install --update || sudo /tmp/aws/install"

echo -e "${YELLOW}📁 Création des répertoires...${NC}"
run_remote "mkdir -p ~/genomic-pipeline/{data,logs,results,models}"
run_remote "mkdir -p ~/genomic-pipeline/data/{training,patients}"

echo -e "${GREEN}✅ Configuration de base terminée!${NC}"
echo -e "${YELLOW}⚠️  Note: Vous devrez vous reconnecter pour que les changements de groupe Docker prennent effet${NC}"

