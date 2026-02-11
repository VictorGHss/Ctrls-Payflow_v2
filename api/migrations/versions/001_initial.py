"""
Alembic migration: Criar tabelas OAuth tokens e contas.

Revision ID: 001_initial
Revises:
Create Date: 2026-02-10

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Criar tabelas iniciais:
    - oauth_tokens (para armazenar access_token e refresh_token criptografados)
    - azul_accounts (para armazenar informações da conta)
    """
    # Criar tabela oauth_tokens
    op.create_table(
        "oauth_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.String(255), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", name="uq_oauth_tokens_account_id"),
    )
    op.create_index("ix_oauth_tokens_account_id", "oauth_tokens", ["account_id"])

    # Criar tabela azul_accounts
    op.create_table(
        "azul_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.String(255), nullable=False),
        sa.Column("owner_name", sa.String(255), nullable=True),
        sa.Column("owner_email", sa.String(255), nullable=True),
        sa.Column("company_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=True),
        sa.Column("connected_at", sa.DateTime(), nullable=True),
        sa.Column("disconnected_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", name="uq_azul_accounts_account_id"),
    )
    op.create_index("ix_azul_accounts_account_id", "azul_accounts", ["account_id"])


def downgrade() -> None:
    """
    Reverter: deletar tabelas.
    """
    op.drop_index("ix_azul_accounts_account_id", table_name="azul_accounts")
    op.drop_table("azul_accounts")
    op.drop_index("ix_oauth_tokens_account_id", table_name="oauth_tokens")
    op.drop_table("oauth_tokens")
