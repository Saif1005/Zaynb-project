#!/bin/bash
# Script complet de déploiement: Setup + Deploy + Terraform

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
INSTANCE_IP="${INSTANCE_IP:-15.188.127.194}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/saif-pipeline-complet}"
SSH_USER="${SSH_USER:-ubuntu}"
AWS_REGION="${AWS_REGION:-eu-west-3}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-622994489865}"
INSTANCE_ID="${INSTANCE_ID:-i-0822e345e78731721}"

# Expanser le tilde dans SSH_KEY si présent
SSH_KEY="${SSH_KEY/#\~/$HOME}"

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Déploiement Complet - Genomic Pipeline              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo -e "  Instance IP: $INSTANCE_IP"
echo -e "  Instance ID: $INSTANCE_ID"
echo -e "  Région AWS: $AWS_REGION"
echo -e "  Account ID: $AWS_ACCOUNT_ID"
echo ""

# Vérifier les prérequis
echo -e "${YELLOW}🔍 Vérification des prérequis...${NC}"

if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI n'est pas installé${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}⚠️  Docker n'est pas disponible localement${NC}"
    echo -e "${YELLOW}   Les images Docker seront construites sur l'instance EC2${NC}"
fi

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}❌ Terraform n'est pas installé${NC}"
    exit 1
fi

if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}❌ Clé SSH non trouvée: $SSH_KEY${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Prérequis OK${NC}"
echo ""

# Étape 1: Setup de l'instance EC2
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Étape 1/4: Configuration de l'instance EC2${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
export INSTANCE_IP SSH_KEY SSH_USER
bash "$(dirname "$0")/setup_ec2_instance.sh"

echo ""

# Étape 2: Build et Push Docker
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Étape 2/4: Build et Push des images Docker${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
export INSTANCE_IP SSH_KEY SSH_USER AWS_REGION AWS_ACCOUNT_ID
bash "$(dirname "$0")/deploy_to_ec2.sh"

echo ""

# Étape 3: Déployer Terraform
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Étape 3/4: Déploiement Terraform${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
cd "$(dirname "$0")/../../terraform"

echo -e "${YELLOW}🔧 Initialisation de Terraform...${NC}"
terraform init

echo -e "${YELLOW}📋 Plan de déploiement...${NC}"
terraform plan

read -p "$(echo -e ${YELLOW}Continuer avec terraform apply? [y/N]: ${NC})" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}🚀 Application des changements...${NC}"
    terraform apply -auto-approve
    echo -e "${GREEN}✅ Terraform déployé${NC}"
else
    echo -e "${YELLOW}⚠️  Terraform apply annulé${NC}"
fi

echo ""

# Étape 4: Vérification
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Étape 4/4: Vérification${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"

echo -e "${YELLOW}🔍 Vérification de l'instance EC2...${NC}"
aws ec2 describe-instances \
    --instance-ids $INSTANCE_ID \
    --region $AWS_REGION \
    --query 'Reservations[0].Instances[0].State.Name' \
    --output text

echo -e "${YELLOW}🔍 Vérification des repositories ECR...${NC}"
aws ecr describe-repositories --region $AWS_REGION --query 'repositories[*].repositoryName' --output table

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ Déploiement terminé avec succès!                  ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📝 Prochaines étapes:${NC}"
echo -e "1. Se connecter à l'instance: ssh -i $SSH_KEY $SSH_USER@$INSTANCE_IP"
echo -e "2. Activer l'environnement: cd ~/genomic-pipeline && source venv/bin/activate"
echo -e "3. Lancer l'API: python scripts/api/start_api_aws.py"
echo -e "4. Ou utiliser l'API via ECS si déployé avec Terraform"

