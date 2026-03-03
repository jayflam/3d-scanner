"""initial tables

Revision ID: 1f84f56caa94
Revises:
Create Date: 2026-02-23 12:21:51.532199

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '1f84f56caa94'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum types
assessment_status = postgresql.ENUM(
    'created', 'uploading', 'extracting_frames', 'splatting',
    'analyzing', 'complete', 'failed',
    name='assessment_status', create_type=False,
)
vehicle_zone = postgresql.ENUM(
    'front_left', 'front_right', 'front_center',
    'rear_left', 'rear_right', 'rear_center',
    'side_left', 'side_right', 'roof',
    'interior_front', 'interior_rear',
    name='vehicle_zone', create_type=False,
)
damage_severity = postgresql.ENUM(
    'minor', 'moderate', 'severe',
    name='damage_severity', create_type=False,
)
processing_stage = postgresql.ENUM(
    'frame_extraction', 'splatting', 'analysis', 'report_generation',
    name='processing_stage', create_type=False,
)
job_status = postgresql.ENUM(
    'queued', 'running', 'complete', 'failed',
    name='job_status', create_type=False,
)


def upgrade() -> None:
    # Create enum types
    assessment_status.create(op.get_bind(), checkfirst=True)
    vehicle_zone.create(op.get_bind(), checkfirst=True)
    damage_severity.create(op.get_bind(), checkfirst=True)
    processing_stage.create(op.get_bind(), checkfirst=True)
    job_status.create(op.get_bind(), checkfirst=True)

    # Assessments table
    op.create_table(
        'assessments',
        sa.Column('id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('claim_number', sa.String(50), nullable=False, index=True),
        sa.Column('agent_id', sa.String(100), nullable=False),
        sa.Column('vin', sa.String(17), server_default=''),
        sa.Column('vehicle_year', sa.Integer(), nullable=False),
        sa.Column('vehicle_make', sa.String(50), nullable=False),
        sa.Column('vehicle_model', sa.String(50), nullable=False),
        sa.Column('status', assessment_status, nullable=False, server_default='created'),
        sa.Column('exterior_video_blob_path', sa.Text(), nullable=True),
        sa.Column('interior_video_blob_path', sa.Text(), nullable=True),
        sa.Column('exterior_splat_blob_path', sa.Text(), nullable=True),
        sa.Column('interior_splat_blob_path', sa.Text(), nullable=True),
        sa.Column('exterior_frame_count', sa.Integer(), server_default='0'),
        sa.Column('interior_frame_count', sa.Integer(), server_default='0'),
        sa.Column('total_estimate_low', sa.Numeric(10, 2), nullable=True),
        sa.Column('total_estimate_high', sa.Numeric(10, 2), nullable=True),
        sa.Column('gps_latitude', sa.Numeric(9, 6), nullable=True),
        sa.Column('gps_longitude', sa.Numeric(9, 6), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # Damage items table
    op.create_table(
        'damage_items',
        sa.Column('id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('assessment_id', sa.UUID(), nullable=False),
        sa.Column('damage_id', sa.String(20), nullable=False),
        sa.Column('location', sa.Text(), nullable=False),
        sa.Column('vehicle_zone', vehicle_zone, nullable=False),
        sa.Column('damage_type', sa.String(100), nullable=False),
        sa.Column('severity', damage_severity, nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('affected_parts', postgresql.JSONB(), server_default='[]'),
        sa.Column('repair_method', sa.Text(), nullable=False),
        sa.Column('estimated_cost_low', sa.Numeric(10, 2), nullable=False),
        sa.Column('estimated_cost_high', sa.Numeric(10, 2), nullable=False),
        sa.Column('confidence_score', sa.Numeric(3, 2), nullable=False),
        sa.Column('reference_frame_paths', postgresql.JSONB(), server_default='[]'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Processing jobs table
    op.create_table(
        'processing_jobs',
        sa.Column('id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('assessment_id', sa.UUID(), nullable=False),
        sa.Column('stage', processing_stage, nullable=False),
        sa.Column('status', job_status, nullable=False, server_default='queued'),
        sa.Column('celery_task_id', sa.String(255), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['assessment_id'], ['assessments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('processing_jobs')
    op.drop_table('damage_items')
    op.drop_table('assessments')

    job_status.drop(op.get_bind(), checkfirst=True)
    processing_stage.drop(op.get_bind(), checkfirst=True)
    damage_severity.drop(op.get_bind(), checkfirst=True)
    vehicle_zone.drop(op.get_bind(), checkfirst=True)
    assessment_status.drop(op.get_bind(), checkfirst=True)
