# core/db.py
import sqlite3
import json
from typing import List, Dict, Any, Optional

DB_NAME = "geotech_piles.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        );
        """)

        # Общий реестр ИГЭ объекта (справочник физико-механических свойств по отчету ИГИ)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS project_ige_registry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            ige_code TEXT NOT NULL,
            soil_type TEXT NOT NULL,
            sand_fraction TEXT,
            sand_density TEXT,
            consistency TEXT,
            density REAL,
            moisture REAL,
            il REAL,
            ip REAL,
            e_ratio REAL,
            friction_angle REAL,
            cohesion REAL,
            e_modulus REAL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            UNIQUE(project_id, ige_code)
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS boreholes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            x REAL,
            y REAL,
            z_collar REAL,
            gw_level REAL,
            note TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS soil_layers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            borehole_id INTEGER NOT NULL,
            ige_code TEXT NOT NULL,
            soil_type TEXT NOT NULL,
            sand_fraction TEXT,
            sand_density TEXT,
            consistency TEXT,
            depth_top REAL NOT NULL,
            depth_bottom REAL NOT NULL,
            density REAL,
            moisture REAL,
            il REAL,
            ip REAL,
            e_ratio REAL,
            friction_angle REAL,
            cohesion REAL,
            e_modulus REAL,
            note TEXT,
            FOREIGN KEY (borehole_id) REFERENCES boreholes(id) ON DELETE CASCADE
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS pile_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            borehole_id INTEGER NOT NULL,
            pile_name TEXT NOT NULL,
            pile_type TEXT NOT NULL,
            length REAL NOT NULL,
            diameter REAL NOT NULL,
            x REAL,
            y REAL,
            same_coords_as_bh INTEGER DEFAULT 1,
            blade_diameter REAL,
            leader_diam REAL,
            leader_depth REAL,
            blow_count INTEGER,
            rest_days INTEGER,
            head_z REAL,
            fu_load REAL,
            fu_settlement REAL,
            curve_data TEXT NOT NULL,
            unload_curve_data TEXT,
            FOREIGN KEY (borehole_id) REFERENCES boreholes(id) ON DELETE CASCADE
        );
        """)

        # Миграция колонок для существующих баз
        cols = [
            ("x", "REAL"),
            ("y", "REAL"),
            ("same_coords_as_bh", "INTEGER DEFAULT 1")
        ]
        for col_name, col_type in cols:
            try:
                cur.execute(f"ALTER TABLE pile_tests ADD COLUMN {col_name} {col_type};")
            except sqlite3.OperationalError:
                pass

        conn.commit()


# --- Проекты ---
def add_project(name: str, desc: str = "") -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO projects (name, description) VALUES (?, ?)", (name, desc))
        conn.commit()
        return cur.lastrowid


def update_project(proj_id: int, name: str, desc: str = ""):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE projects SET name = ?, description = ? WHERE id = ?", (name, desc, proj_id))
        conn.commit()


def get_all_projects() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM projects ORDER BY name ASC")
        return [dict(r) for r in cur.fetchall()]


def delete_project(proj_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", (proj_id,))
        conn.commit()


# --- Реестр ИГЭ объекта ---
def get_project_ige_registry(project_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM project_ige_registry WHERE project_id = ? ORDER BY ige_code ASC", (project_id,))
        return [dict(r) for r in cur.fetchall()]


def upsert_project_ige(project_id: int, layer_data: dict):
    """Добавляет или обновляет характеристики ИГЭ в реестре объекта."""
    if not layer_data.get('ige_code'):
        return
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO project_ige_registry 
            (project_id, ige_code, soil_type, sand_fraction, sand_density, consistency, 
             density, moisture, il, ip, e_ratio, friction_angle, cohesion, e_modulus)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, ige_code) DO UPDATE SET
                soil_type=excluded.soil_type,
                sand_fraction=excluded.sand_fraction,
                sand_density=excluded.sand_density,
                consistency=excluded.consistency,
                density=COALESCE(excluded.density, density),
                moisture=COALESCE(excluded.moisture, moisture),
                il=COALESCE(excluded.il, il),
                ip=COALESCE(excluded.ip, ip),
                e_ratio=COALESCE(excluded.e_ratio, e_ratio),
                friction_angle=COALESCE(excluded.friction_angle, friction_angle),
                cohesion=COALESCE(excluded.cohesion, cohesion),
                e_modulus=COALESCE(excluded.e_modulus, e_modulus);
        """, (
            project_id, layer_data['ige_code'], layer_data['soil_type'],
            layer_data.get('sand_fraction'), layer_data.get('sand_density'), layer_data.get('consistency'),
            layer_data.get('density'), layer_data.get('moisture'), layer_data.get('il'), layer_data.get('ip'),
            layer_data.get('e_ratio'), layer_data.get('friction_angle'), layer_data.get('cohesion'),
            layer_data.get('e_modulus')
        ))
        conn.commit()


# --- Скважины ---
def save_borehole(project_id: int, name: str, x: Optional[float], y: Optional[float],
                  z: Optional[float], gw_level: Optional[float], note: str,
                  layers: list, bh_id: Optional[int] = None) -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        if bh_id:
            cur.execute("""
                UPDATE boreholes SET project_id=?, name=?, x=?, y=?, z_collar=?, gw_level=?, note=? 
                WHERE id=?
            """, (project_id, name, x, y, z, gw_level, note, bh_id))
            cur.execute("DELETE FROM soil_layers WHERE borehole_id=?", (bh_id,))
        else:
            cur.execute("""
                INSERT INTO boreholes (project_id, name, x, y, z_collar, gw_level, note) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (project_id, name, x, y, z, gw_level, note))
            bh_id = cur.lastrowid

        for l in layers:
            cur.execute("""
                INSERT INTO soil_layers 
                (borehole_id, ige_code, soil_type, sand_fraction, sand_density, consistency, depth_top, depth_bottom,
                 density, moisture, il, ip, e_ratio, friction_angle, cohesion, e_modulus, note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bh_id, l['ige_code'], l['soil_type'], l.get('sand_fraction'), l.get('sand_density'),
                l.get('consistency'), l['depth_top'], l['depth_bottom'], l.get('density'), l.get('moisture'),
                l.get('il'), l.get('ip'), l.get('e_ratio'), l.get('friction_angle'),
                l.get('cohesion'), l.get('e_modulus'), l.get('note')
            ))
            # Синхронизируем ИГЭ со справочником объекта
            upsert_project_ige(project_id, l)

        conn.commit()
        return bh_id


def delete_borehole(bh_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM boreholes WHERE id = ?", (bh_id,))
        conn.commit()


def get_boreholes_by_project(project_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM boreholes WHERE project_id = ? ORDER BY name ASC", (project_id,))
        return [dict(r) for r in cur.fetchall()]


def get_all_boreholes() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT b.*, p.name as project_name FROM boreholes b JOIN projects p ON b.project_id = p.id ORDER BY p.name, b.name")
        return [dict(r) for r in cur.fetchall()]


def get_borehole_by_id(bh_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM boreholes WHERE id = ?", (bh_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_borehole_layers(bh_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM soil_layers WHERE borehole_id = ? ORDER BY depth_top ASC", (bh_id,))
        return [dict(r) for r in cur.fetchall()]


# --- Сваи ---
def save_pile_test(borehole_id: int, name: str, p_type: str, length: float,
                   diam: float, head_z: Optional[float], fu_load: Optional[float],
                   fu_settlement: Optional[float], points: list,
                   x: Optional[float] = None, y: Optional[float] = None, same_coords_as_bh: bool = True,
                   unload_points: Optional[list] = None,
                   blade_diameter: Optional[float] = None,
                   leader_diam: Optional[float] = None,
                   leader_depth: Optional[float] = None,
                   blow_count: Optional[int] = None,
                   rest_days: Optional[int] = None,
                   pile_id: Optional[int] = None) -> int:
    with get_connection() as conn:
        cur = conn.cursor()
        curve_json = json.dumps(points)
        unload_json = json.dumps(unload_points) if unload_points else None
        same_c_int = 1 if same_coords_as_bh else 0

        if pile_id:
            cur.execute("""
                UPDATE pile_tests SET 
                    borehole_id=?, pile_name=?, pile_type=?, length=?, diameter=?, blade_diameter=?,
                    x=?, y=?, same_coords_as_bh=?, leader_diam=?, leader_depth=?, blow_count=?, rest_days=?,
                    head_z=?, fu_load=?, fu_settlement=?, curve_data=?, unload_curve_data=?
                WHERE id=?
            """, (borehole_id, name, p_type, length, diam, blade_diameter,
                  x, y, same_c_int, leader_diam, leader_depth, blow_count, rest_days,
                  head_z, fu_load, fu_settlement, curve_json, unload_json, pile_id))
        else:
            cur.execute("""
                INSERT INTO pile_tests 
                (borehole_id, pile_name, pile_type, length, diameter, blade_diameter, 
                 x, y, same_coords_as_bh, leader_diam, leader_depth, blow_count, rest_days,
                 head_z, fu_load, fu_settlement, curve_data, unload_curve_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (borehole_id, name, p_type, length, diam, blade_diameter,
                  x, y, same_c_int, leader_diam, leader_depth, blow_count, rest_days,
                  head_z, fu_load, fu_settlement, curve_json, unload_json))
            pile_id = cur.lastrowid
        conn.commit()
        return pile_id


def delete_pile_test(pile_id: int):
    with get_connection() as conn:
        conn.execute("DELETE FROM pile_tests WHERE id = ?", (pile_id,))
        conn.commit()


def get_pile_tests_by_borehole(borehole_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM pile_tests WHERE borehole_id = ?", (borehole_id,))
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            r['curve_data'] = json.loads(r['curve_data'])
            r['unload_curve_data'] = json.loads(r['unload_curve_data']) if r.get('unload_curve_data') else []
        return rows