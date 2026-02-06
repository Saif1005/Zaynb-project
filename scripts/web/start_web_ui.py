#!/usr/bin/env python3
"""Interface web simple avec Streamlit pour upload et visualisation."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
from loguru import logger
from config.logging_config import logging_config
from src.agents.orchestrator import OrchestratorAgent
from config.aws_config import aws_config

# Setup logging
logging_config.setup_logging()

st.set_page_config(
    page_title="Pipeline de Détection de Cancer",
    page_icon="🧬",
    layout="wide"
)

st.title("🧬 Pipeline Agentic AI - Détection de Cancer")
st.markdown("""
Uploadez vos fichiers FASTQ et le système exécutera automatiquement :
1. Pipeline Parabricks (fq2bam + HaplotypeCaller)
2. Analyse des variants
3. Fine-tuning du modèle Mistral (optionnel)
4. Prédiction de cancer
5. Génération du rapport
""")

# Sidebar configuration
with st.sidebar:
    st.header("Configuration")
    patient_id = st.text_input("ID Patient", value="PATIENT001")
    instance_id = st.text_input("Instance EC2 ID", value="i-0581b617f72d0c155")
    ssh_key_path = st.text_input("Chemin clé SSH", value="~/.ssh/genomic-pipeline")
    train_llm = st.checkbox("Fine-tuner le modèle Mistral", value=False)

# Main content
st.header("Upload des Fichiers FASTQ")

col1, col2 = st.columns(2)

with col1:
    fastq_r1 = st.file_uploader("FASTQ R1", type=["fastq", "fastq.gz", "fq", "fq.gz"])

with col2:
    fastq_r2 = st.file_uploader("FASTQ R2 (optionnel)", type=["fastq", "fastq.gz", "fq", "fq.gz"])

if st.button("🚀 Lancer le Pipeline", type="primary"):
    if not fastq_r1:
        st.error("Veuillez uploader au moins le fichier FASTQ R1")
    elif not patient_id:
        st.error("Veuillez entrer un ID patient")
    else:
        with st.spinner("Exécution du pipeline en cours..."):
            try:
                # Save uploaded files temporarily
                import tempfile
                temp_dir = Path(tempfile.mkdtemp())
                fastq_r1_path = temp_dir / fastq_r1.name
                fastq_r2_path = temp_dir / fastq_r2.name if fastq_r2 else None
                
                with open(fastq_r1_path, "wb") as f:
                    f.write(fastq_r1.read())
                
                if fastq_r2:
                    with open(fastq_r2_path, "wb") as f:
                        f.write(fastq_r2.read())
                
                # Prepare context
                context = {
                    "patient_id": patient_id,
                    "fastq_r1": str(fastq_r1_path),
                    "fastq_r2": str(fastq_r2_path) if fastq_r2_path else None,
                    "instance_id": instance_id,
                    "ssh_key": ssh_key_path,
                    "train_llm": train_llm,
                }
                
                # Initialize orchestrator
                config = {
                    "instance_id": instance_id,
                    "ssh_key": ssh_key_path,
                    "auto_train": train_llm,
                }
                
                orchestrator = OrchestratorAgent(config=config)
                result = orchestrator.run(context)
                
                # Display results
                if result.success:
                    st.success("✅ Pipeline terminé avec succès!")
                    
                    # Display prediction
                    if "results" in result.data:
                        pred = result.data["results"]
                        st.header("📊 Résultats de la Prédiction")
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Cancer détecté", "OUI" if pred.get('cancer_detected') else "NON")
                        with col2:
                            st.metric("Niveau de risque", pred.get('risk_level', 'N/A'))
                        with col3:
                            st.metric("Score de risque", f"{pred.get('risk_score', 0):.1f}/100")
                        
                        if pred.get('cancer_detected'):
                            st.subheader("Types de cancer")
                            st.write(", ".join(pred.get('cancer_types', [])))
                            
                            if pred.get('recommendations'):
                                st.subheader("Recommandations")
                                for rec in pred.get('recommendations', []):
                                    st.write(f"• {rec}")
                    
                    # Display report
                    if "report_path" in result.data:
                        st.header("📄 Rapport")
                        report_path = result.data["report_path"]
                        st.success(f"Rapport généré: {report_path}")
                        
                        if Path(report_path).exists():
                            with open(report_path, "rb") as f:
                                st.download_button(
                                    "Télécharger le rapport",
                                    f.read(),
                                    file_name=Path(report_path).name,
                                    mime="application/pdf" if report_path.endswith(".pdf") else "text/html"
                                )
                else:
                    st.error(f"❌ Pipeline échoué: {result.error}")
                    
            except Exception as e:
                st.error(f"Erreur: {e}")
                logger.error(f"Pipeline execution error: {e}")

# Status section
st.header("📈 Statut du Pipeline")
st.info("Le pipeline s'exécute étape par étape. Surveillez les logs ci-dessous.")








