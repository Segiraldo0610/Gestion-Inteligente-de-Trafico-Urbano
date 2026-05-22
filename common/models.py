from dataclasses import dataclass, asdict
import json


@dataclass
class EventoCamara:
    sensor_id: str
    interseccion: str
    volumen: int
    velocidad_promedio: float
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class EventoEspira:
    sensor_id: str
    interseccion: str
    vehiculos_contados: int
    intervalo_segundos: int
    timestamp_inicio: str
    timestamp_fin: str

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class EventoGPS:
    sensor_id: str
    interseccion: str
    nivel_congestion: str
    velocidad_promedio: float
    timestamp: str

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class ComandoSemaforo:
    interseccion: str
    estado: str
    duracion: int
    motivo: str

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)
