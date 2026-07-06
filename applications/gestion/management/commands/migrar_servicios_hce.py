import pyodbc

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model

from applications.entidades.models import Servicio


def limpiar_texto(valor):
    if valor is None:
        return None
    valor = str(valor).strip()
    return valor if valor else None


def limpiar_nombre(valor):
    valor = limpiar_texto(valor)
    return valor.title() if valor else ""


class Command(BaseCommand):
    help = "Migra servicios desde SQL Server HCE.dbo.Servicios hacia Servicio"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--confirm", action="store_true")
        parser.add_argument("--limit", type=int)
        parser.add_argument("--usuario", type=str)
        parser.add_argument("--batch-size", type=int, default=1000)

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        confirm = options["confirm"]
        limit = options["limit"]
        usuario_username = options["usuario"]
        batch_size = options["batch_size"]

        if not dry_run and not confirm:
            self.stdout.write(self.style.ERROR(
                "Usá --dry-run para probar o --confirm para migrar en serio."
            ))
            return

        usuario_migracion = None

        if usuario_username:
            User = get_user_model()

            try:
                usuario_migracion = User.objects.get(username=usuario_username)
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"No existe el usuario: {usuario_username}"
                ))
                return

        conn_str = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=192.168.180.254,1433;"
            "DATABASE=HCE;"
            "UID=UsrSantaClaraRead;"
            "PWD=5@nt@k1@r@;"
            "TrustServerCertificate=yes;"
        )

        top = f"TOP {limit}" if limit else ""

        sql = f"""
            SELECT {top}
                s.Nombre
            FROM dbo.Servicios s
            WHERE s.ActivoActualmente = 1
              AND s.Nombre NOT LIKE '%manuel%'
              AND s.Estado = 'A'
        """

        creados = 0
        actualizados = 0
        omitidos = 0
        errores = 0
        procesados = 0

        self.stdout.write("Conectando a SQL Server...")

        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        cursor.execute(sql)

        try:
            with transaction.atomic():
                while True:
                    filas = cursor.fetchmany(batch_size)

                    if not filas:
                        break

                    columnas = [col[0] for col in cursor.description]

                    for fila in filas:
                        data = dict(zip(columnas, fila))
                        procesados += 1

                        try:
                            nombre = limpiar_nombre(data.get("Nombre"))

                            if not nombre:
                                omitidos += 1
                                continue

                            defaults = {}
 

                            servicio = Servicio.objects.filter(
                                nombre__iexact=nombre
                            ).first()

                            if servicio:
                                for campo, valor in defaults.items():
                                    setattr(servicio, campo, valor)

                                servicio.save()
                                actualizados += 1
                            else: 

                                Servicio.objects.create(
                                    nombre=nombre, 
                                )
                                creados += 1

                        except Exception as e:
                            errores += 1
                            self.stdout.write(self.style.ERROR(
                                f"Error procesando servicio {data.get('Nombre')}: {e}"
                            ))

                    self.stdout.write(
                        f"Procesados: {procesados} | Creados: {creados} | "
                        f"Actualizados: {actualizados} | Omitidos: {omitidos} | Errores: {errores}"
                    )

                if dry_run:
                    raise Exception("DRY RUN: rollback intencional")

        except Exception as e:
            if dry_run:
                self.stdout.write(self.style.WARNING(
                    "Dry-run finalizado. No se guardó nada."
                ))
            else:
                raise e

        finally:
            cursor.close()
            conn.close()

        self.stdout.write(self.style.SUCCESS(
            f"Finalizado | Procesados: {procesados} | Creados: {creados} | "
            f"Actualizados: {actualizados} | Omitidos: {omitidos} | Errores: {errores}"
        ))