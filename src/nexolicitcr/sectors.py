"""Editable commercial specialties, never official SICOP classification codes.

Keep IDs stable: saved profiles reference them. Terms are explicit suggestions,
not inferred capabilities; updating this list never rewrites confirmed profiles.
"""

SECTORS = {
    "technology": {
        "label": "Tecnología e informática",
        "specialties": {
            "networks": (
                "Redes informáticas y cableado",
                ["redes informáticas", "redes de datos", "cableado estructurado"],
            ),
            "software": (
                "Software y aplicaciones",
                ["software", "desarrollo web", "aplicaciones web"],
            ),
            "support": (
                "Soporte y mantenimiento de equipos",
                [
                    "soporte informático",
                    "mantenimiento informático",
                    "mantenimiento de computadoras",
                ],
            ),
            "hardware": (
                "Computadoras, servidores y periféricos",
                [
                    "equipo de cómputo",
                    "equipos de cómputo",
                    "computadoras portátiles",
                    "servidores informáticos",
                ],
            ),
            "cybersecurity": (
                "Ciberseguridad y protección de datos",
                ["ciberseguridad", "seguridad informática", "seguridad de la información"],
            ),
            "cloud": (
                "Servicios en la nube y alojamiento web",
                ["servicios en la nube", "infraestructura en la nube", "alojamiento web"],
            ),
        },
    },
    "sports": {
        "label": "Deporte y recreación",
        "specialties": {
            "goal_nets": (
                "Redes para arcos y porterías",
                ["redes para arcos", "redes para porterías", "redes de fútbol"],
            ),
            "equipment": (
                "Equipamiento deportivo",
                ["equipamiento deportivo", "implementos deportivos"],
            ),
            "recreation": (
                "Actividades recreativas y deportivas",
                ["actividades recreativas", "actividades deportivas", "talleres deportivos"],
            ),
        },
    },
    "marketing": {
        "label": "Comunicación y mercadeo",
        "specialties": {
            "social": ("Gestión de redes sociales", ["redes sociales", "gestión de comunidades"]),
            "advertising": ("Publicidad y diseño gráfico", ["publicidad", "diseño gráfico"]),
            "audiovisual": (
                "Producción audiovisual y fotografía",
                ["producción audiovisual", "producción de videos", "servicios de fotografía"],
            ),
        },
    },
    "facilities": {
        "label": "Limpieza y mantenimiento",
        "specialties": {
            "cleaning": (
                "Limpieza de instalaciones",
                [
                    "limpieza de instalaciones",
                    "limpieza de edificios",
                    "servicio de limpieza",
                    "aseo y limpieza",
                ],
            ),
            "gardens": (
                "Jardinería y zonas verdes",
                ["jardinería", "mantenimiento de zonas verdes"],
            ),
            "pest_control": (
                "Control de plagas y fumigación",
                ["control de plagas", "servicio de fumigación", "servicios de fumigación"],
            ),
            "air_conditioning": (
                "Aire acondicionado y refrigeración",
                ["aire acondicionado", "aires acondicionados", "equipos de refrigeración"],
            ),
            "cleaning_supplies": (
                "Productos e insumos de limpieza",
                [
                    "productos de limpieza",
                    "insumos de limpieza",
                    "líquido limpiador",
                    "líquido desengrasante",
                ],
            ),
        },
    },
    "construction": {
        "label": "Construcción y obras",
        "specialties": {
            "civil": (
                "Obra civil e infraestructura pública",
                [
                    "obra civil",
                    "obras públicas",
                    "construcción de infraestructura",
                    "construcción de edificios",
                    "construcción de vestidores",
                    "construcción de plazoletas",
                    "construcción de aceras",
                    "mantenimiento de edificios",
                ],
            ),
            "buildings": (
                "Construcción y remodelación de edificios",
                [
                    "construcción de edificios",
                    "construcción de instalaciones",
                    "construcción (obra civil)",
                    "remodelación de edificios",
                    "remodelación de oficinas",
                ],
            ),
            "electrical": (
                "Instalaciones eléctricas e iluminación",
                [
                    "instalaciones eléctricas",
                    "redes eléctricas",
                    "instalación de luminarias",
                    "iluminación de canchas",
                    "alimentadores trifásicos",
                ],
            ),
            "roads": (
                "Caminos, pavimentos y obra vial",
                [
                    "mantenimiento de vías",
                    "mejoramiento del camino",
                    "pavimentación",
                    "carpeta asfáltica",
                    "construcción de aceras",
                ],
            ),
            "water": (
                "Acueductos y alcantarillado",
                [
                    "redes de agua potable",
                    "redes de alcantarillado",
                    "construcción de acueductos",
                    "alcantarillado pluvial",
                ],
            ),
            "materials": (
                "Materiales de construcción y madera",
                [
                    "materiales de construcción",
                    "madera y plywood",
                    "regla de madera",
                    "láminas de plywood",
                ],
            ),
            "metalwork": (
                "Portones, verjas y estructuras metálicas",
                [
                    "portones y verjas",
                    "fabricación de portones",
                    "estructuras metálicas",
                    "cerramientos metálicos",
                ],
            ),
        },
    },
    "food": {
        "label": "Alimentación",
        "specialties": {
            "catering": (
                "Preparación de alimentos y catering",
                [
                    "catering",
                    "preparación de alimentos",
                    "servicio de alimentación",
                    "servicios de alimentación",
                ],
            ),
            "supplies": (
                "Suministro de alimentos",
                ["suministro de alimentos", "productos alimenticios"],
            ),
            "kitchen": (
                "Equipo y utensilios de cocina",
                [
                    "equipo de cocina",
                    "equipos de cocina",
                    "utensilios de cocina",
                    "cocinas industriales",
                ],
            ),
        },
    },
    "furniture": {
        "label": "Mobiliario",
        "specialties": {
            "office": ("Mobiliario de oficina", ["muebles de oficina", "mobiliario de oficina"]),
            "school": (
                "Mobiliario escolar y educativo",
                ["mobiliario escolar", "mobiliario educativo", "pupitres", "mesas escolares"],
            ),
            "shelving": (
                "Estanterías y archivos",
                [
                    "estantería metálica",
                    "estanterías metálicas",
                    "archivos metálicos",
                    "archivadores metálicos",
                ],
            ),
        },
    },
    "health": {
        "label": "Salud y equipo médico",
        "specialties": {
            "medical_supplies": (
                "Insumos y material médico",
                [
                    "insumos médicos",
                    "material médico",
                    "material de curación",
                    "guantes quirúrgicos",
                ],
            ),
            "medical_equipment": (
                "Equipo médico y su mantenimiento",
                ["equipo médico", "equipos médicos", "equipo biomédico", "equipos biomédicos"],
            ),
            "dental": (
                "Equipo e insumos odontológicos",
                ["insumos odontológicos", "equipo odontológico", "materiales dentales"],
            ),
            "clinical": (
                "Laboratorio y análisis clínicos",
                ["análisis clínicos", "laboratorio clínico", "reactivos de laboratorio"],
            ),
        },
    },
    "security": {
        "label": "Seguridad física y prevención",
        "specialties": {
            "guarding": (
                "Vigilancia y seguridad privada",
                [
                    "seguridad privada",
                    "servicio de vigilancia",
                    "servicios de vigilancia",
                    "vigilancia física",
                ],
            ),
            "video": (
                "Videovigilancia y control de acceso",
                [
                    "videovigilancia",
                    "cámaras de seguridad",
                    "control de acceso",
                    "circuito cerrado de televisión",
                ],
            ),
            "fire": (
                "Protección y equipos contra incendios",
                [
                    "sistemas contra incendios",
                    "equipos contra incendios",
                    "extintores",
                    "detección de incendios",
                ],
            ),
        },
    },
    "transport": {
        "label": "Transporte y logística",
        "specialties": {
            "passengers": (
                "Transporte de personas",
                ["transporte de personas", "transporte de pasajeros", "transporte de estudiantes"],
            ),
            "freight": (
                "Transporte de carga y mudanzas",
                [
                    "transporte de carga",
                    "servicio de mudanza",
                    "servicios de mudanza",
                    "servicios de mudanzas",
                ],
            ),
            "courier": (
                "Mensajería y paquetería",
                ["servicio de mensajería", "servicios de mensajería", "servicios de paquetería"],
            ),
            "logistics": (
                "Almacenamiento y distribución",
                ["almacenamiento y distribución", "operaciones logísticas", "alquiler de bodegas"],
            ),
        },
    },
    "vehicles": {
        "label": "Vehículos y taller automotriz",
        "specialties": {
            "maintenance": (
                "Mantenimiento y reparación de vehículos",
                [
                    "mantenimiento de vehículos",
                    "reparación de vehículos",
                    "mantenimiento vehicular",
                    "mecánica automotriz",
                ],
            ),
            "parts": (
                "Repuestos y accesorios vehiculares",
                ["repuestos para vehículos", "repuestos automotrices", "accesorios vehiculares"],
            ),
            "tires": (
                "Llantas y servicios de alineado",
                [
                    "llantas para vehículos",
                    "llantas radiales",
                    "alineado y balanceo",
                    "alineación y balanceo",
                ],
            ),
        },
    },
    "education": {
        "label": "Educación y capacitación",
        "specialties": {
            "training": (
                "Capacitación y formación profesional",
                [
                    "servicios de capacitación",
                    "curso de certificación",
                    "formación profesional",
                    "capacitación en seguridad informática",
                    "curso de RCP",
                    "capacitación en ISO 17025",
                ],
            ),
            "languages": (
                "Cursos de idiomas y traducción",
                [
                    "cursos de idiomas",
                    "cursos de inglés",
                    "servicios de traducción",
                    "servicios de interpretación",
                ],
            ),
            "educational_material": (
                "Material didáctico y libros educativos",
                [
                    "material didáctico",
                    "materiales didácticos",
                    "libros educativos",
                    "libros de texto",
                ],
            ),
        },
    },
    "professional": {
        "label": "Consultoría y servicios profesionales",
        "specialties": {
            "legal": (
                "Servicios jurídicos y notariales",
                ["asesoría jurídica", "servicios jurídicos", "servicios notariales"],
            ),
            "accounting": (
                "Contabilidad y auditoría financiera",
                ["servicios contables", "auditoría financiera", "auditoría de estados financieros"],
            ),
            "engineering": (
                "Diseño, inspección y estudios de ingeniería",
                [
                    "diseño arquitectónico",
                    "inspección de obras",
                    "estudios de ingeniería",
                    "levantamiento topográfico",
                ],
            ),
        },
    },
    "environment": {
        "label": "Ambiente y gestión de residuos",
        "specialties": {
            "waste": (
                "Recolección y tratamiento de residuos",
                [
                    "recolección de residuos",
                    "gestión de residuos",
                    "tratamiento de residuos",
                    "residuos peligrosos",
                ],
            ),
            "water_analysis": (
                "Análisis y tratamiento de agua",
                [
                    "análisis de agua",
                    "análisis de aguas",
                    "tratamiento de aguas residuales",
                    "calidad del agua",
                ],
            ),
            "environmental_studies": (
                "Estudios y consultoría ambiental",
                ["estudios ambientales", "consultoría ambiental", "impacto ambiental"],
            ),
        },
    },
    "agriculture": {
        "label": "Agro, veterinaria y recursos forestales",
        "specialties": {
            "agricultural_supplies": (
                "Insumos y herramientas agrícolas",
                [
                    "insumos agrícolas",
                    "herramientas agrícolas",
                    "abonos orgánicos",
                    "semillas certificadas",
                ],
            ),
            "veterinary": (
                "Servicios e insumos veterinarios",
                [
                    "servicios veterinarios",
                    "medicamentos veterinarios",
                    "insumos veterinarios",
                    "alimento para animales",
                ],
            ),
            "forestry": (
                "Reforestación y manejo forestal",
                ["reforestación", "manejo forestal", "viveros forestales", "plantas forestales"],
            ),
        },
    },
    "textiles": {
        "label": "Textiles, uniformes y protección personal",
        "specialties": {
            "uniforms": (
                "Confección y suministro de uniformes",
                ["confección de uniformes", "suministro de uniformes", "uniformes institucionales"],
            ),
            "protective_clothing": (
                "Ropa y equipo de protección personal",
                [
                    "equipo de protección personal",
                    "equipos de protección personal",
                    "calzado de seguridad",
                    "zapatos de seguridad",
                    "ropa de protección",
                ],
            ),
        },
    },
    "office_supplies": {
        "label": "Papelería e impresión",
        "specialties": {
            "stationery": (
                "Papelería y útiles de oficina",
                [
                    "útiles de oficina",
                    "artículos de oficina",
                    "papel bond",
                    "suministros de papelería",
                ],
            ),
            "printing_supplies": (
                "Impresión y consumibles",
                [
                    "servicios de impresión",
                    "cartuchos de tinta",
                    "cartuchos de tóner",
                    "tóner para impresora",
                ],
            ),
        },
    },
    "industrial": {
        "label": "Maquinaria y equipo industrial",
        "specialties": {
            "machinery": (
                "Maquinaria pesada y repuestos",
                ["maquinaria pesada", "maquinaria industrial", "repuestos para maquinaria"],
            ),
            "tools": (
                "Herramientas y equipo de taller",
                [
                    "herramientas eléctricas",
                    "herramientas manuales",
                    "equipo de taller",
                    "equipos de soldadura",
                ],
            ),
            "pumps": (
                "Bombas, válvulas y equipos de bombeo",
                [
                    "bombas de agua",
                    "equipos de bombeo",
                    "bombas sumergibles",
                    "bombas centrífugas",
                    "válvulas electromecánicas",
                ],
            ),
        },
    },
    "events": {
        "label": "Eventos y producción cultural",
        "specialties": {
            "production": (
                "Producción de eventos y decoración",
                [
                    "producción de eventos",
                    "organización de eventos",
                    "decoración navideña",
                    "figuras inflables",
                ],
            ),
            "sound": (
                "Sonido, iluminación y escenarios",
                [
                    "equipo de sonido",
                    "equipos de sonido",
                    "iluminación para eventos",
                    "alquiler de tarimas",
                ],
            ),
        },
    },
    "other": {
        "label": "Otra actividad · definir mi especialidad",
        "specialties": {
            "custom": ("Mi especialidad no está en la lista", []),
        },
    },
}


def specialty_terms(sector, specialty):
    if not sector and not specialty:
        return None  # Legacy profiles remain editable.
    if sector not in SECTORS or specialty not in SECTORS[sector]["specialties"]:
        raise ValueError("Elegí una especialidad que pertenezca al sector seleccionado.")
    return list(SECTORS[sector]["specialties"][specialty][1])


def selected_specialties(values=None, sector="", specialty=""):
    """Validate stable sector:specialty IDs; accept old single-choice forms/profiles."""
    if values is None:
        specialty_terms(sector, specialty)
        return [f"{sector}:{specialty}"] if sector else []
    if not 1 <= len(values) <= 8 or len(set(values)) != len(values):
        raise ValueError("Elegí entre 1 y 8 especialidades diferentes.")
    for value in values:
        if len(value) > 81 or value.count(":") != 1:
            raise ValueError("Especialidad inválida.")
        specialty_terms(*value.split(":"))
    return list(values)


def combined_terms(selections):
    return list(
        dict.fromkeys(
            term for selection in selections for term in specialty_terms(*selection.split(":"))
        )
    )
