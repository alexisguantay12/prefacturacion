import pyodbc

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from applications.entidades.models import ObraSocial, Plan


def limpiar_texto(valor):
    if valor is None:
        return None

    valor = str(valor).strip()

    if not valor:
        return None

    return " ".join(valor.split())


class Command(BaseCommand):
    help = "Migra obras sociales y planes desde SQL Server HCE hacia ObraSocial y Plan"

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

        sql_obras_sociales = f"""
            SELECT {top}
                m.Id,
                m.NombreHabitual
            FROM dbo.Mutuales m
            WHERE m.ActivoActualmente = 1
              AND m.Estado = 'A'
              AND m.NombreHabitual IS NOT NULL
            ORDER BY m.NombreHabitual
        """

        sql_planes = f"""
            SELECT {top}
                mp.Nombre AS NombrePlan,
                mp.IdMutual,
                m.NombreHabitual
            FROM dbo.Mutual_Planes mp
            INNER JOIN dbo.Mutuales m
                ON m.Id = mp.IdMutual
            WHERE mp.ActivoActualmente = 1
              AND mp.Estado = 'A'
              AND mp.Nombre IS NOT NULL
              AND m.ActivoActualmente = 1
              AND m.Estado = 'A'
            ORDER BY m.NombreHabitual, mp.Nombre
        """

        obras_creadas = 0
        obras_actualizadas = 0
        obras_omitidas = 0

        planes_creados = 0
        planes_actualizados = 0
        planes_omitidos = 0

        errores = 0
        procesados_obras = 0
        procesados_planes = 0

        obras_sociales_por_id_sql = {}

        self.stdout.write("Conectando a SQL Server...")

        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        try:
            with transaction.atomic():
                self.stdout.write("Migrando obras sociales...")

                cursor.execute(sql_obras_sociales)

                while True:
                    filas = cursor.fetchmany(batch_size)

                    if not filas:
                        break

                    columnas = [col[0] for col in cursor.description]

                    for fila in filas:
                        data = dict(zip(columnas, fila))
                        procesados_obras += 1

                        try:
                            id_mutual = data.get("Id")
                            nombre = limpiar_texto(data.get("NombreHabitual"))

                            if not id_mutual or not nombre:
                                obras_omitidas += 1
                                continue

                            obra_social = ObraSocial.objects.filter(nombre=nombre).first()

                            if obra_social:
                                obras_actualizadas += 1
                            else:
                                obra_social = ObraSocial.objects.create(
                                    nombre=nombre,
                                    sigla=None,
                                    descripcion=None
                                )
                                obras_creadas += 1

                            obras_sociales_por_id_sql[id_mutual] = obra_social

                        except Exception as e:
                            errores += 1
                            self.stdout.write(self.style.ERROR(
                                f"Error migrando obra social {data.get('NombreHabitual')}: {e}"
                            ))

                    self.stdout.write(
                        f"Obras procesadas: {procesados_obras} | "
                        f"Creadas: {obras_creadas} | "
                        f"Existentes: {obras_actualizadas} | "
                        f"Omitidas: {obras_omitidas} | "
                        f"Errores: {errores}"
                    )

                self.stdout.write("Migrando planes...")

                cursor.execute(sql_planes)

                while True:
                    filas = cursor.fetchmany(batch_size)

                    if not filas:
                        break

                    columnas = [col[0] for col in cursor.description]

                    for fila in filas:
                        data = dict(zip(columnas, fila))
                        procesados_planes += 1

                        try:
                            nombre_plan = limpiar_texto(data.get("NombrePlan"))
                            id_mutual = data.get("IdMutual")

                            if not nombre_plan or not id_mutual:
                                planes_omitidos += 1
                                continue

                            obra_social = obras_sociales_por_id_sql.get(id_mutual)

                            if not obra_social:
                                nombre_obra = limpiar_texto(data.get("NombreHabitual"))

                                if nombre_obra:
                                    obra_social = ObraSocial.objects.filter(
                                        nombre=nombre_obra
                                    ).first()

                            if not obra_social:
                                planes_omitidos += 1
                                continue

                            defaults = {
                                "obra_social": obra_social,
                            }

                            if usuario_migracion:
                                defaults["user_updated"] = usuario_migracion

                            plan = Plan.objects.filter(
                                nombre=nombre_plan,
                                obra_social=obra_social
                            ).first()

                            if plan:
                                for campo, valor in defaults.items():
                                    setattr(plan, campo, valor)

                                plan.save()
                                planes_actualizados += 1
                            else:
                                if usuario_migracion:
                                    defaults["user_made"] = usuario_migracion

                                Plan.objects.create(
                                    nombre=nombre_plan,
                                    **defaults
                                )
                                planes_creados += 1

                        except Exception as e:
                            errores += 1
                            self.stdout.write(self.style.ERROR(
                                f"Error migrando plan {data.get('NombrePlan')}: {e}"
                            ))

                    self.stdout.write(
                        f"Planes procesados: {procesados_planes} | "
                        f"Creados: {planes_creados} | "
                        f"Actualizados: {planes_actualizados} | "
                        f"Omitidos: {planes_omitidos} | "
                        f"Errores: {errores}"
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
            f"Finalizado | "
            f"Obras procesadas: {procesados_obras} | "
            f"Obras creadas: {obras_creadas} | "
            f"Obras existentes: {obras_actualizadas} | "
            f"Obras omitidas: {obras_omitidas} | "
            f"Planes procesados: {procesados_planes} | "
            f"Planes creados: {planes_creados} | "
            f"Planes actualizados: {planes_actualizados} | "
            f"Planes omitidos: {planes_omitidos} | "
            f"Errores: {errores}"
        ))