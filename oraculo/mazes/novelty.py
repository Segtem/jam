import math
from typing import Dict, List, Tuple


def behavior_vector(desc: Dict[str, float]) -> Tuple[float, ...]:
    """
    Construye un vector de comportamiento numérico (huella de longitud fija) 
    para evaluar cómo se juega un nivel, a partir de un diccionario de descripción.

    Los campos extraídos, y su orden estable (12 elementos), son:
    1. solution_length (normalizado / 20.0)
    2. verticality
    3. n_floors (normalizado / 4.0)
    4. height_span (normalizado / 4.0)
    5. interest_score
    6. n_doors
    7. n_gates
    8. n_hazards
    9. lock_depth
    10. portal_steps
    11. fall_steps
    12. impossibility_degree

    Si algún campo no está presente en el diccionario, asume por defecto un valor de 0.

    Args:
        desc (dict): Diccionario con las métricas o propiedades del nivel.

    Returns:
        tuple[float, ...]: Una tupla de 12 elementos de tipo float en el orden documentado.
    """
    return (
        float(desc.get("solution_length", 0.0) / 20.0),
        float(desc.get("verticality", 0.0)),
        float(desc.get("n_floors", 0.0) / 4.0),
        float(desc.get("height_span", 0.0) / 4.0),
        float(desc.get("interest_score", 0.0)),
        float(desc.get("n_doors", 0.0)),
        float(desc.get("n_gates", 0.0)),
        float(desc.get("n_hazards", 0.0)),
        float(desc.get("lock_depth", 0.0)),
        float(desc.get("portal_steps", 0.0)),
        float(desc.get("fall_steps", 0.0)),
        float(desc.get("impossibility_degree", 0.0)),
    )


def novelty_score(vec: Tuple[float, ...], others: List[Tuple[float, ...]], k: int = 3) -> float:
    """
    Calcula el grado de novedad de un vector como la distancia euclidiana media 
    a sus `k` vecinos más cercanos en la lista `others`.

    - Si `others` está vacío, la novedad se considera máxima y devuelve 1e9.
    - Si hay menos de `k` elementos en `others`, promedia sobre todos los disponibles.
    - Utiliza la distancia euclidiana estándar entre tuplas.

    Args:
        vec (tuple[float, ...]): Vector de comportamiento a evaluar.
        others (list[tuple[float, ...]]): Lista de vectores de comportamiento existentes.
        k (int): Número de vecinos más cercanos a considerar. Por defecto es 3.

    Returns:
        float: Distancia euclidiana media a los k vecinos más cercanos, 
               o 1e9 si la lista de otros vectores está vacía.
    """
    if not others:
        return 1e9
    
    distances = []
    for other_vec in others:
        # Cálculo de distancia euclidiana estándar
        dist = math.sqrt(sum((v1 - v2) ** 2 for v1, v2 in zip(vec, other_vec)))
        distances.append(dist)
    
    # Ordenar distancias de menor a mayor para encontrar los vecinos más cercanos
    distances.sort()
    
    # Tomar los k vecinos más cercanos (o todos los disponibles si len(others) < k)
    nearest = distances[:k]
    
    # Devolver el promedio de las distancias
    return sum(nearest) / len(nearest)
