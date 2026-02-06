"""Report Generator Agent - Generates comprehensive reports."""

from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import json
from loguru import logger

from src.agents.base_agent import BaseAgent, AgentResult, AgentStatus
from src.aws.s3_manager import get_s3_manager
from config.aws_config import aws_config
from config.reporting_config import reporting_config


class ReportGeneratorAgent(BaseAgent):
    """Agent for generating comprehensive reports."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Report Generator Agent."""
        super().__init__("ReportGenerator", config)
        self.s3_manager = get_s3_manager()

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Validate input context."""
        # Report generation is optional, always return True
        return True

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        Generate comprehensive report from all pipeline results.

        Args:
            context: Context with all pipeline results

        Returns:
            AgentResult with report path
        """
        patient_id = context.get("patient_id")
        
        try:
            # Collect all data for report
            report_data = {
                "patient_id": patient_id,
                "report_date": datetime.now().isoformat(),
                "pipeline_version": "1.0",
                
                # Parabricks results
                "parabricks": {
                    "bam_s3": context.get("bam_s3"),
                    "vcf_s3": context.get("vcf_s3"),
                },
                
                # VCF Analysis results
                "variant_analysis": {
                    "total_variants": context.get("total_variants", 0),
                    "pathogenic_cancer_variants": context.get("pathogenic_cancer_variants", 0),
                    "coverage": context.get("coverage", 0),
                    "summary": context.get("summary", {}),
                },
                
                # Prediction results
                "prediction": context.get("prediction_results", {}),
                
                # Model info
                "model": {
                    "model_path": context.get("model_path"),
                    "model_trained": context.get("model_trained", False),
                },
            }
            
            # Generate report based on format
            report_format = reporting_config.format
            
            if report_format == "json":
                report_path = self._generate_json_report(report_data, patient_id)
            elif report_format == "html":
                report_path = self._generate_html_report(report_data, patient_id)
            else:  # PDF
                report_path = self._generate_pdf_report(report_data, patient_id)
            
            # Upload report to S3
            s3_key = f"reports/{patient_id}/report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{report_format}"
            report_s3 = self.s3_manager.upload_file(
                report_path,
                s3_key,
                bucket_name=aws_config.s3_output_bucket
            )
            
            self.logger.info(f"✓ Report generated and uploaded: {report_s3}")
            
            return AgentResult(
                success=True,
                status=AgentStatus.COMPLETED,
                data={
                    "report_path": report_path,
                    "report_s3": report_s3,
                    "report_format": report_format,
                }
            )

        except Exception as e:
            error_msg = f"Report generation failed: {e}"
            self.logger.error(error_msg)
            # Don't fail pipeline if report generation fails
            return AgentResult(
                success=False,
                status=AgentStatus.FAILED,
                error=error_msg
            )

    def _generate_json_report(self, data: Dict, patient_id: str) -> str:
        """Generate JSON report."""
        report_path = reporting_config.get_patient_report_path(patient_id)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return str(report_path)

    def _generate_html_report(self, data: Dict, patient_id: str) -> str:
        """Generate HTML report."""
        report_path = reporting_config.get_patient_report_path(patient_id)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        html_content = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Rapport Génétique - {patient_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #2c3e50; }}
        .section {{ margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 5px; }}
        .variant {{ margin: 10px 0; padding: 10px; background: white; border-left: 4px solid #3498db; }}
        .prediction {{ padding: 15px; background: {'#ffebee' if data['prediction'].get('cancer_detected') else '#e8f5e9'}; }}
    </style>
</head>
<body>
    <h1>Rapport d'Analyse Génétique</h1>
    <div class="section">
        <h2>Informations Patient</h2>
        <p><strong>ID Patient:</strong> {patient_id}</p>
        <p><strong>Date:</strong> {data['report_date']}</p>
    </div>
    
    <div class="section">
        <h2>Résultats Parabricks</h2>
        <p><strong>BAM:</strong> {data['parabricks'].get('bam_s3', 'N/A')}</p>
        <p><strong>VCF:</strong> {data['parabricks'].get('vcf_s3', 'N/A')}</p>
    </div>
    
    <div class="section">
        <h2>Analyse des Variants</h2>
        <p><strong>Total variants:</strong> {data['variant_analysis']['total_variants']}</p>
        <p><strong>Variants pathogènes:</strong> {data['variant_analysis']['pathogenic_cancer_variants']}</p>
        <p><strong>Couverture:</strong> {data['variant_analysis']['coverage']:.1f}x</p>
    </div>
    
    <div class="section prediction">
        <h2>Prédiction de Cancer</h2>
        <p><strong>Cancer détecté:</strong> {'OUI' if data['prediction'].get('cancer_detected') else 'NON'}</p>
        {f"<p><strong>Types de cancer:</strong> {', '.join(data['prediction'].get('cancer_types', []))}</p>" if data['prediction'].get('cancer_detected') else ''}
        <p><strong>Niveau de risque:</strong> {data['prediction'].get('risk_level', 'N/A')}</p>
        <p><strong>Score de risque:</strong> {data['prediction'].get('risk_score', 0):.1f}/100</p>
    </div>
</body>
</html>
"""
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(report_path)

    def _generate_pdf_report(self, data: Dict, patient_id: str) -> str:
        """Generate PDF report (simplified, use HTML for now)."""
        # For now, generate HTML and suggest conversion
        # In production, use fpdf2 or reportlab
        html_path = self._generate_html_report(data, patient_id)
        self.logger.info("PDF generation: Using HTML format (PDF conversion can be added)")
        return html_path








