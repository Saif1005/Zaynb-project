# 🚀 Prochaines Étapes - Déploiement

## ✅ État Actuel

- ✅ Instance EC2 configurée : `i-0822e345e78731721` (15.188.127.194)
- ✅ Clé SSH configurée : `~/.ssh/saif-pipeline-complet`
- ✅ Scripts de déploiement prêts
- ✅ Terraform : Infrastructure partiellement déployée (VPC, S3, IAM, CloudWatch)
- ✅ Corrections des permissions IAM appliquées (voir `terraform/PERMISSIONS.md`)

## 📋 Option 1 : Déploiement Complet (Recommandé)

### Étape 1 : Lancer le déploiement avec variables explicites

```bash
cd /mnt/c/Users/saifa/projet_zaynb

# Définir les variables explicitement pour éviter les conflits
export INSTANCE_IP=15.188.127.194
export SSH_KEY=$HOME/.ssh/saif-pipeline-complet
export SSH_USER=ubuntu
export AWS_REGION=eu-west-3

# Lancer le déploiement
bash scripts/deployment/deploy_complete.sh
```

### Ce que fait le script :

1. **Configuration de l'instance EC2** (5-10 min)
   - Mise à jour système Ubuntu
   - Installation Docker
   - Installation Python 3.12
   - Installation AWS CLI
   - Création des répertoires

2. **Build et Push Docker** (10-15 min)
   - Build images `genomic-api` et `genomic-agent`
   - Push vers ECR (eu-west-3)

3. **Déploiement Terraform** (optionnel, 5-10 min)
   - Infrastructure AWS (VPC, S3, IAM, etc.)

4. **Vérification**
   - Test de l'instance
   - Vérification ECR

## 📋 Option 2 : Déploiement Étape par Étape

### Étape 1 : Configuration de l'instance

```bash
export INSTANCE_IP=15.188.127.194
export SSH_KEY=$HOME/.ssh/saif-pipeline-complet
export SSH_USER=ubuntu

bash scripts/deployment/setup_ec2_instance.sh
```

### Étape 2 : Build et Push Docker

```bash
export INSTANCE_IP=15.188.127.194
export SSH_KEY=$HOME/.ssh/saif-pipeline-complet
export SSH_USER=ubuntu
export AWS_REGION=eu-west-3
export AWS_ACCOUNT_ID=622994489865

bash scripts/deployment/deploy_to_ec2.sh
```

### Étape 3 : Finaliser le déploiement Terraform

```bash
cd terraform

# Si vous avez des erreurs de permissions, utilisez -refresh=false
terraform plan -refresh=false

# Appliquer les changements
terraform apply -refresh=false

# Note: Les buckets S3 sont protégés contre la suppression (prevent_destroy)
# Voir terraform/PERMISSIONS.md pour plus de détails
```

## 🔧 Dépannage

### Si vous voyez encore l'ancienne IP (15.237.252.85)

```bash
# Vérifier les variables d'environnement
env | grep INSTANCE_IP
env | grep SSH_KEY

# Les supprimer si elles existent
unset INSTANCE_IP SSH_KEY

# Relancer avec variables explicites
export INSTANCE_IP=15.188.127.194
export SSH_KEY=$HOME/.ssh/saif-pipeline-complet
bash scripts/deployment/deploy_complete.sh
```

### Si la clé SSH n'est pas trouvée

```bash
# Vérifier que la clé existe
ls -la ~/.ssh/saif-pipeline-complet

# Si elle n'existe pas, la copier depuis Windows
cp /mnt/c/Users/saifa/Downloads/saif-pipeline-complet.pem ~/.ssh/saif-pipeline-complet
chmod 400 ~/.ssh/saif-pipeline-complet
```

## ✅ Vérification Post-Déploiement

### 1. Se connecter à l'instance

```bash
ssh -i ~/.ssh/saif-pipeline-complet ubuntu@15.188.127.194
```

### 2. Vérifier l'installation

```bash
# Sur l'instance
docker --version
python3.12 --version
aws --version
cd ~/genomic-pipeline && ls -la
```

### 3. Tester l'API (si déployée)

```bash
# Sur l'instance
cd ~/genomic-pipeline
source venv/bin/activate
python scripts/api/start_api_aws.py
```

## 📝 Notes Importantes

- Le déploiement complet prend environ **20-30 minutes**
- L'instance doit être en cours d'exécution
- Assurez-vous d'avoir les permissions AWS appropriées
- Les images Docker peuvent être volumineuses (plusieurs GB)

## 🆘 Support

Si vous rencontrez des problèmes :
1. Vérifiez les logs du script
2. Vérifiez la connexion SSH : `ssh -i ~/.ssh/saif-pipeline-complet ubuntu@15.188.127.194`
3. Vérifiez les logs CloudWatch sur AWS Console


