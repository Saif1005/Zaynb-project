# Scripts de Déploiement

## Configuration Actuelle

- **Instance ID**: `i-0822e345e78731721`
- **Public IP**: `15.188.127.194`
- **Private IP**: `172.31.7.218`
- **Région**: `eu-west-3`
- **Clé SSH par défaut**: `~/.ssh/saif-pipeline-complet`

## Vérification de la Clé SSH

Si la clé SSH n'est pas trouvée, vérifiez son nom exact :

```bash
ls -la ~/.ssh/
```

Si votre clé a un nom différent, vous pouvez la spécifier :

```bash
export SSH_KEY=~/.ssh/votre-nom-de-cle.pem
bash scripts/deployment/deploy_complete.sh
```

## Utilisation

### Déploiement Complet

```bash
bash scripts/deployment/deploy_complete.sh
```

### Déploiement Étape par Étape

1. **Configuration de l'instance** :
```bash
export INSTANCE_IP=15.188.127.194
export SSH_KEY=~/.ssh/saif-pipeline-complet
bash scripts/deployment/setup_ec2_instance.sh
```

2. **Déploiement de l'application** :
```bash
bash scripts/deployment/deploy_to_ec2.sh
```

## Variables d'Environnement

Vous pouvez surcharger les valeurs par défaut :

- `INSTANCE_IP` : Adresse IP publique de l'instance
- `SSH_KEY` : Chemin vers la clé SSH privée
- `SSH_USER` : Utilisateur SSH (par défaut: `ec2-user`)
- `AWS_REGION` : Région AWS (par défaut: `eu-west-3`)
- `AWS_ACCOUNT_ID` : ID du compte AWS (par défaut: `622994489865`)




