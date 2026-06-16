"""Configuration runtime production — chemins absolus EBS (sans relatifs)."""

import os
from pathlib import Path
from pydantic import BaseModel, Field, field_validator


class RuntimeConfig(BaseModel):
    """Chemins montés sur l'instance g4dn.xlarge (volume EBS gp3)."""

    data_mount: Path = Field(
        default=Path(os.getenv("RUNTIME_DATA_MOUNT", "/mnt/data"))
    )
    ref_mount: Path = Field(
        default=Path(os.getenv("RUNTIME_REF_MOUNT", "/mnt/data/references"))
    )
    scratch_mount: Path = Field(
        default=Path(os.getenv("RUNTIME_SCRATCH_MOUNT", "/mnt/data/scratch"))
    )
    work_mount: Path = Field(
        default=Path(os.getenv("RUNTIME_WORK_MOUNT", "/mnt/data/work"))
    )

    @field_validator("data_mount", "ref_mount", "scratch_mount", "work_mount")
    @classmethod
    def _absolute_only(cls, v: Path) -> Path:
        p = Path(v).resolve()
        if not p.is_absolute():
            raise ValueError(f"Chemin absolu requis: {v}")
        return p

    def docker_volume_args(self) -> list[str]:
        """Arguments -v Docker pour tous les montages runtime."""
        mounts = {self.data_mount, self.ref_mount, self.scratch_mount, self.work_mount}
        args: list[str] = []
        for m in sorted(mounts):
            args.extend(["-v", f"{m}:{m}"])
        return args


runtime_config = RuntimeConfig()
