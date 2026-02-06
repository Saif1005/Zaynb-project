#!/usr/bin/env python3
"""Script Python pour vérifier l'état du pipeline sur l'instance EC2."""

import paramiko
import sys
from pathlib import Path
from typing import Optional

# Configuration
INSTANCE_IP = "15.188.127.194"
SSH_KEY_PATH = Path.home() / ".ssh" / "saif-pipeline-complet"
SSH_USER = "ubuntu"
WORK_DIR = "/tmp/genomic_pipeline"


def execute_remote_command(ssh_client, command: str, timeout: int = 30) -> tuple[int, str, str]:
    """Execute a command on the remote instance."""
    stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
    exit_code = stdout.channel.recv_exit_status()
    stdout_text = stdout.read().decode('utf-8').strip()
    stderr_text = stderr.read().decode('utf-8').strip()
    return exit_code, stdout_text, stderr_text


def check_file_exists(ssh_client, filepath: str) -> bool:
    """Check if a file exists on the remote instance."""
    exit_code, _, _ = execute_remote_command(ssh_client, f"test -f {filepath}")
    return exit_code == 0


def get_file_size(ssh_client, filepath: str) -> Optional[str]:
    """Get file size in human-readable format."""
    exit_code, stdout, _ = execute_remote_command(ssh_client, f"du -h {filepath} 2>/dev/null | cut -f1")
    if exit_code == 0 and stdout:
        return stdout
    return None


def main():
    """Main verification function."""
    print("🔍 Vérification de l'état du pipeline sur l'instance EC2")
    print("=" * 60)
    print(f"Instance: {INSTANCE_IP}")
    print(f"Répertoire de travail: {WORK_DIR}")
    print()

    # Connect to instance
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            INSTANCE_IP,
            username=SSH_USER,
            key_filename=str(SSH_KEY_PATH),
            timeout=10
        )
        print("✅ Connexion SSH établie")
        print()
    except Exception as e:
        print(f"❌ Erreur de connexion: {e}")
        sys.exit(1)

    try:
        # 1. Check tools
        print("1️⃣ Vérification des outils installés...")
        print("-" * 40)
        
        tools = {
            "BWA": "command -v bwa && bwa 2>&1 | head -3",
            "samtools": "command -v samtools && samtools --version | head -2",
            "Docker": "command -v docker && docker --version",
        }
        
        for tool_name, cmd in tools.items():
            exit_code, stdout, stderr = execute_remote_command(ssh, cmd)
            if exit_code == 0:
                print(f"✅ {tool_name}: {stdout.split(chr(10))[0] if stdout else 'Installé'}")
            else:
                print(f"❌ {tool_name}: Non installé")
        print()

        # 2. Check reference genome
        print("2️⃣ Vérification du génome de référence...")
        print("-" * 40)
        
        ref_file = f"{WORK_DIR}/reference.fa"
        if check_file_exists(ssh, ref_file):
            size = get_file_size(ssh, ref_file)
            print(f"✅ Génome de référence présent: {size}")
            
            # Check indexes
            indexes = {
                "Index BWA (.bwt)": f"{ref_file}.bwt",
                "Index FASTA (.fai)": f"{ref_file}.fai",
                "Dictionnaire (.dict)": f"{WORK_DIR}/reference.dict",
            }
            
            for index_name, index_path in indexes.items():
                if check_file_exists(ssh, index_path):
                    print(f"   ✅ {index_name}: Présent")
                else:
                    print(f"   ⚠️ {index_name}: Absent")
        else:
            print("❌ Génome de référence absent")
        print()

        # 3. Check FASTQ files
        print("3️⃣ Vérification des fichiers FASTQ...")
        print("-" * 40)
        
        for fastq in ["R1.fastq.gz", "R2.fastq.gz"]:
            fastq_path = f"{WORK_DIR}/{fastq}"
            if check_file_exists(ssh, fastq_path):
                size = get_file_size(ssh, fastq_path)
                print(f"✅ {fastq}: {size}")
            else:
                print(f"⚠️ {fastq}: Absent (peut être en cours de téléchargement)")
        print()

        # 4. Check alignment files
        print("4️⃣ Vérification des fichiers d'alignement...")
        print("-" * 40)
        
        alignment_files = {
            "aligned.sam": "SAM (alignement brut)",
            "aligned.sorted.bam": "BAM trié",
            "aligned.sorted.bam.bai": "Index BAM",
        }
        
        for filename, description in alignment_files.items():
            filepath = f"{WORK_DIR}/{filename}"
            if check_file_exists(ssh, filepath):
                size = get_file_size(ssh, filepath)
                print(f"✅ {description} ({filename}): {size}")
            else:
                print(f"⚠️ {description} ({filename}): Absent")
        print()

        # 5. Check VCF file
        print("5️⃣ Vérification du fichier VCF...")
        print("-" * 40)
        
        vcf_file = f"{WORK_DIR}/output.vcf"
        if check_file_exists(ssh, vcf_file):
            size = get_file_size(ssh, vcf_file)
            # Count variants (non-header lines)
            exit_code, stdout, _ = execute_remote_command(
                ssh, f"grep -v '^#' {vcf_file} 2>/dev/null | wc -l"
            )
            variant_count = stdout.strip() if exit_code == 0 else "0"
            print(f"✅ output.vcf: {size}")
            print(f"   Variants détectés: {variant_count}")
        else:
            print("⚠️ output.vcf: Absent (GATK pas encore terminé)")
        print()

        # 6. Check running processes
        print("6️⃣ Vérification des processus en cours...")
        print("-" * 40)
        
        processes = {
            "BWA": "bwa",
            "samtools": "samtools",
            "GATK": "gatk|GATK|docker.*gatk",
            "AWS S3": "aws s3",
        }
        
        for proc_name, pattern in processes.items():
            exit_code, stdout, _ = execute_remote_command(
                ssh, f"ps aux | grep -E '{pattern}' | grep -v grep || echo ''"
            )
            if stdout.strip():
                print(f"🔄 {proc_name}: En cours d'exécution")
                # Show first process line
                first_line = stdout.split('\n')[0][:80]
                print(f"   {first_line}...")
            else:
                print(f"⏸️ {proc_name}: Aucun processus")
        print()

        # 7. Check system resources
        print("7️⃣ Vérification des ressources système...")
        print("-" * 40)
        
        # CPU
        exit_code, stdout, _ = execute_remote_command(ssh, "top -bn1 | grep 'Cpu(s)' | head -1")
        if stdout:
            print(f"CPU: {stdout}")
        
        # Memory
        exit_code, stdout, _ = execute_remote_command(ssh, "free -h | grep -E 'Mem|Swap'")
        if stdout:
            for line in stdout.split('\n'):
                print(f"   {line}")
        
        # Disk
        exit_code, stdout, _ = execute_remote_command(ssh, "df -h / | tail -1")
        if stdout:
            print(f"Disque: {stdout}")
        print()

        # 8. Check S3 files
        print("8️⃣ Vérification des fichiers sur S3...")
        print("-" * 40)
        
        s3_commands = {
            "BAM": "aws s3 ls s3://genomic-cancer-pipeline-output-dev-622994489865/patients/PATIENT001/ --region eu-west-3 2>/dev/null | grep -E '\\.bam|\\.bai'",
            "VCF": "aws s3 ls s3://genomic-cancer-pipeline-output-dev-622994489865/patients/PATIENT001/ --region eu-west-3 2>/dev/null | grep '\\.vcf'",
        }
        
        for file_type, cmd in s3_commands.items():
            exit_code, stdout, _ = execute_remote_command(ssh, cmd)
            if stdout.strip():
                print(f"✅ {file_type} sur S3:")
                for line in stdout.strip().split('\n'):
                    print(f"   {line}")
            else:
                print(f"⚠️ {file_type}: Non trouvé sur S3")
        print()

        print("✅ Vérification terminée")
        print("=" * 60)

    finally:
        ssh.close()


if __name__ == "__main__":
    main()
