# Terraform Infrastructure for Genomic Cancer Detection Pipeline

Infrastructure as Code pour déployer le pipeline génomique sur AWS.

## Structure

```
terraform/
├── main.tf                    # Configuration principale
├── variables.tf               # Variables
├── outputs.tf                 # Outputs
├── modules/
│   ├── vpc/                   # VPC, subnets, NAT gateway
│   ├── s3/                    # S3 buckets
│   ├── iam/                   # IAM roles et policies
│   └── batch/                 # AWS Batch (optionnel)
└── environments/
    ├── dev/                   # Configuration dev
    └── prod/                  # Configuration prod
```

## Prérequis

1. **Terraform** >= 1.0
2. **AWS CLI** configuré
3. **Credentials AWS** (via AWS CLI ou variables d'environnement)

## Utilisation

### 1. Initialiser Terraform

```bash
cd terraform/environments/dev  # ou prod
terraform init
```

### 2. Planifier les changements

```bash
terraform plan
```

### 3. Appliquer l'infrastructure

```bash
terraform apply
```

### 4. Voir les outputs

```bash
terraform output
```

## Modules

### VPC Module

Crée:
- VPC avec DNS
- 2 subnets publics (multi-AZ)
- 2 subnets privés (multi-AZ)
- Internet Gateway
- NAT Gateway (optionnel)
- Route tables

### S3 Module

Crée 3 buckets:
- **Input**: Fichiers FASTQ d'entrée
- **Output**: Résultats (BAM, VCF)
- **Reference**: Génome de référence

**Fonctionnalités:**
- Versioning activé
- Encryption (AES256)
- Public access bloqué
- Lifecycle policies (transition vers Glacier)

### IAM Module

Crée:
- **EC2 Instance Role**: Accès S3 et CloudWatch
- **Batch Execution Role**: Pour jobs Batch
- **Batch Service Role**: Pour AWS Batch service

### Batch Module (Optionnel)

Crée:
- Compute environment (EC2 avec GPU)
- Job queue
- Job definition pour Parabricks

## Configuration par Environnement

### Development (`environments/dev/`)

- Logs retention: 7 jours
- SSH: Ouvert à tous (pour développement)
- Batch: Désactivé
- Coûts réduits

### Production (`environments/prod/`)

- Logs retention: 90 jours
- SSH: Restreint (CIDR blocks)
- Batch: Activé
- Sécurité renforcée

## Variables Importantes

| Variable | Description | Défaut |
|----------|-------------|--------|
| `environment` | dev ou prod | - |
| `aws_region` | Région AWS | us-east-1 |
| `vpc_cidr` | CIDR VPC | 10.0.0.0/16 |
| `ec2_instance_type` | Type instance GPU | p3.2xlarge |
| `enable_batch` | Activer AWS Batch | false |

## Outputs

Après `terraform apply`, récupérer:

```bash
# Buckets S3
terraform output s3_input_bucket_name
terraform output s3_output_bucket_name

# IAM Roles
terraform output ec2_instance_role_arn

# VPC
terraform output vpc_id
terraform output public_subnet_ids
```

## Backend S3 (Optionnel)

Pour stocker le state Terraform sur S3:

1. Créer un bucket S3 pour le state
2. Créer `terraform.tfbackend`:

```hcl
bucket = "genomic-cancer-pipeline-terraform-state"
key    = "terraform.tfstate"
region = "us-east-1"
encrypt = true
```

3. Initialiser avec backend:

```bash
terraform init -backend-config=terraform.tfbackend
```

## Coûts Estimés

### Infrastructure de base (par mois)

- **VPC/NAT Gateway**: ~$32/mois (NAT Gateway)
- **S3 Storage**: ~$0.023/GB/mois
- **CloudWatch Logs**: ~$0.50/GB ingestion

### Compute (à l'usage)

- **EC2 p3.2xlarge**: ~$3.06/h (on-demand)
- **AWS Batch**: Même tarif que EC2

## Sécurité

### Bonnes Pratiques

1. **SSH Access**: Restreindre `allowed_ssh_cidrs` en production
2. **S3 Encryption**: Activé par défaut
3. **IAM Roles**: Utiliser roles plutôt que credentials
4. **VPC**: Isoler les ressources dans VPC privé
5. **Security Groups**: Limiter les accès

### À Faire

- [ ] Configurer WAF si API Gateway utilisé
- [ ] Activer VPC Flow Logs
- [ ] Configurer CloudTrail
- [ ] Mettre en place backup automatique

## Dépannage

### Erreur: "Bucket already exists"

Les buckets S3 doivent être globalement uniques. Modifier les noms dans `terraform.tfvars`.

### Erreur: "Insufficient instance capacity"

Les instances GPU peuvent être limitées. Essayer une autre région ou utiliser Spot instances.

### Erreur: "IAM role not found"

Vérifier que les modules IAM sont créés avant les ressources qui les utilisent.

## Destruction

Pour détruire l'infrastructure:

```bash
terraform destroy
```

**Attention**: Cela supprimera toutes les ressources, y compris les données S3.

## Maintenance

### Mettre à jour l'infrastructure

```bash
terraform plan
terraform apply
```

### Ajouter de nouvelles ressources

1. Modifier les fichiers `.tf`
2. `terraform plan` pour vérifier
3. `terraform apply` pour appliquer

## Support

Pour questions ou problèmes, voir:
- Documentation Terraform: https://www.terraform.io/docs
- Documentation AWS: https://docs.aws.amazon.com










