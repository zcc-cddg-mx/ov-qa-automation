import os
import oracledb


def policy_conn():
    """Conexión Oracle para ren-data (ECU_POLICY)."""
    return oracledb.connect(
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        dsn=_oracle_dsn(os.environ["DB_DSN"]),
    )


def rule_conn():
    """Conexión Oracle para rules (ECU_RULE)."""
    return oracledb.connect(
        user=os.environ["DB_RULE_USER"],
        password=os.environ["DB_RULE_PASSWORD"],
        dsn=_oracle_dsn(os.environ["DB_DSN"]),
    )


def _oracle_dsn(jdbc: str) -> str:
    """Convierte jdbc:oracle:thin:@host:port:sid → host:port/sid para oracledb."""
    # formato: jdbc:oracle:thin:@10.225.196.6:1521:ariuat
    part = jdbc.split("@", 1)[1]          # 10.225.196.6:1521:ariuat
    host, port, sid = part.split(":")
    return f"{host}:{port}/{sid}"
