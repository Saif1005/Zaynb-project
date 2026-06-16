"""Tests détection variants pathogènes panel sein."""

from src.preprocessing.vcf_parser import VCFParser


def test_pathogenic_brca_panel_intersection():
    parser = VCFParser(
        "data/test/patient_pathogenic_brca.vcf",
        min_quality=10.0,
        min_vaf=0.01,
        min_depth=2,
        require_pass=False,
    )
    variants = parser.parse()
    assert len(variants) == 2

    matched, genes = parser.intersect_breast_panel_pathogenic_variants(variants)
    assert len(matched) == 2
    assert "BRCA1" in genes
    assert "BRCA2" in genes
    assert all(v.is_pathogenic for v in matched)


def test_format_tuple_af_ad_from_pyvcf():
    """pyvcf3 renvoie souvent AF/AD en tuple — ne doit pas casser le parsing."""
    from src.preprocessing.vcf_parser import Variant, VCFParser

    v = Variant(
        chromosome="17",
        position=43044295,
        ref="C",
        alt="T",
        quality=950.5,
        filter_status="PASS",
        format_data={"GT": (0, 1), "DP": (45,), "AD": (23, 22), "AF": (0.489,)},
        gene="BRCA1",
        clinvar="Pathogenic",
    )
    assert v.depth == 45
    assert abs(v.vaf - 0.489) < 0.001
    assert v.is_pathogenic

    parser = VCFParser.__new__(VCFParser)
    parser.cancer_genes_db = __import__(
        "src.database.cancer_genes_db", fromlist=["get_cancer_genes_db"]
    ).get_cancer_genes_db()
    parser._breast_panel_cache = None
    parser.min_quality = 10
    parser.min_vaf = 0.01
    parser.min_depth = 2
    parser.require_pass = False
    parser.vcf_path = None

    matched, genes = parser.intersect_breast_panel_pathogenic_variants([v])
    assert len(matched) == 1
    assert genes == ["BRCA1"]


def test_sample_brca_pathogenic():
    parser = VCFParser(
        "data/test/sample_brca.vcf",
        min_quality=10.0,
        min_vaf=0.01,
        min_depth=2,
        require_pass=False,
    )
    variants = parser.parse()
    matched, genes = parser.intersect_breast_panel_pathogenic_variants(variants)
    assert len(matched) >= 1
    assert "BRCA1" in genes
