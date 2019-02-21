from config_db import db_conn, run_query
from datasets_config import DatasetsConfig
import datetime
import errno
import json
import os
import psycopg2
from psycopg2 import extras as psycopg2_extras, sql as psycopg2_sql
import requests
import shutil
import subprocess
import time
import urllib.request


renamed = {
    'files': [],
    'timbuctoo_tables': [],
    'reconciliation_jobs': [],
}
to_delete = {
    'files': [],
    'timbuctoo_tables': [],
    'reconciliation_jobs': [],
}


def execute_rename_pg_dataset(pg_type, old_name, new_name):
    print('Renaming %s "%s" to "%s".' % (pg_type.lower(), old_name, new_name))
    with conn.cursor() as cur:
        cur.execute(psycopg2_sql.SQL('ALTER {} {} RENAME TO {}').format(
            psycopg2_sql.SQL(pg_type),
            psycopg2_sql.Identifier(old_name),
            psycopg2_sql.Identifier(new_name),
        ))
    conn.commit()


def rename(timbuctoo_tables=None, reconciliation_jobs=None, revert=False):
    def rename_pg_dataset(pg_type, old_name):
        new_name = old_name + '_backup'
        if revert:
            new_name, old_name = old_name, new_name
        try:
            execute_rename_pg_dataset(pg_type, old_name, new_name)
        except psycopg2.ProgrammingError as e:
            if revert:
                print('Error found when renaming %s to %s: %s' % (old_name, new_name, e))
            else:
                raise

    if timbuctoo_tables:
        for table_name in timbuctoo_tables:
            rename_pg_dataset('VIEW', table_name + '_expanded')
            rename_pg_dataset('TABLE', table_name)

            table_name_entry_old = table_name
            table_name_entry_new = table_name + '_backup'
            if revert:
                table_name_entry_old, table_name_entry_new = table_name_entry_new, table_name_entry_old

            print('Renaming timbuctoo table entry "%s" to "%s"' % (table_name_entry_old, table_name_entry_new))

            rename_sql = '''
                UPDATE timbuctoo_tables
                    SET "table_name" = %s,
                        "collection_id" = {}
                WHERE "table_name" = %s
                '''.format('left("collection_id", -7)' if revert else '"collection_id" || \'_backup\'')
            with conn.cursor() as cur:
                cur.execute(rename_sql, (table_name_entry_new, table_name_entry_old))

            conn.commit()

        if not revert:
            renamed['timbuctoo_tables'] += timbuctoo_tables

    if reconciliation_jobs:
        for job_id in reconciliation_jobs:
            old_job_id = job_id
            new_job_id = job_id + '_backup'
            if revert:
                old_job_id, new_job_id = new_job_id, old_job_id

            print('Renaming reconciliation job "%s" to "%s"' % (old_job_id, new_job_id))
            with conn.cursor() as cur:
                cur.execute('DELETE FROM reconciliation_jobs WHERE job_id = %s', (new_job_id,))
                cur.execute('UPDATE reconciliation_jobs SET job_id = %s WHERE job_id = %s',
                            (new_job_id, old_job_id))
            print('Renaming schema "job_%s" to "job_%s"' % (old_job_id, new_job_id))
            try:
                with conn.cursor() as cur:
                    cur.execute(psycopg2_sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(
                        psycopg2_sql.Identifier('job_' + new_job_id)
                    ))
                    cur.execute(psycopg2_sql.SQL('ALTER SCHEMA {} RENAME TO {}').format(
                        psycopg2_sql.Identifier('job_' + old_job_id),
                        psycopg2_sql.Identifier('job_' + new_job_id)
                    ))
            except psycopg2.ProgrammingError as e:
                print(e)
                conn.rollback()
            else:
                conn.commit()

        if not revert:
            renamed['reconciliation_jobs'] += reconciliation_jobs


if __name__ == '__main__':
    print('Reading test config...')
    with open('/app/test_config.json', 'r') as config_file:
        config_data = json.load(config_file)
    print('Test config loaded.')

    while True:
        print('Starting test cycle at %s...' % str(datetime.datetime.now()))

        job_id = None
        try:
            print('Preparing collections...')
            with db_conn() as conn:
                for resource in config_data['resources']:
                    collection = DatasetsConfig().dataset(resource['dataset_id']).collection(resource['collection_id'])
                    with conn.cursor() as cur:
                        cur.execute('SELECT 1 FROM timbuctoo_tables WHERE "table_name" = %s', (collection.table_name,))
                        tim_tab = cur.fetchone()
                    conn.commit()
                    if tim_tab == (1,):
                        print('Entry for collection %s found. Renaming.' % collection.table_name)
                        rename(timbuctoo_tables=[collection.table_name])
                    else:
                        print('No entry found for collection %s. Adding to delete list.' % collection.table_name)
                        to_delete['timbuctoo_tables'].append(collection.table_name)

                with conn.cursor(cursor_factory=psycopg2_extras.RealDictCursor) as cur:
                    cur.execute('SELECT job_id, status FROM reconciliation_jobs')
                    recon_jobs = cur.fetchall()
                conn.commit()

            print('Posting job.')
            response = requests.post("http://web_server:8000/handle_json_upload/", json=config_data)
            job_id = response.json()['job_id']
            print('Job posted. Got job_id %s.' % job_id)

            job_done = False
            for job in recon_jobs:
                if job['job_id'] == job_id:
                    if job['status'].lower().startswith(('failed', 'finished')):
                        print('Job already done, renaming and reposting.')
                        rename(reconciliation_jobs=[job['job_id']])
                        response = requests.post("http://web_server:8000/handle_json_upload/", json=config_data)
                        job_id = response.json()['job_id']
                    else:
                        print('Job already requested, using that one.')
                    job_done = True
                    break
            if not job_done:
                print('Test job freshly inserted.')
                to_delete['reconciliation_jobs'].append(job_id)

            print('Giving test job higher priority.')
            with conn.cursor() as cur:
                cur.execute("UPDATE reconciliation_jobs SET requested_at = TIMESTAMP '-infinity' WHERE job_id = %s",
                            (job_id,))
            conn.commit()

            start_time = time.time()
            while True:
                print('Checking job status...')
                response = requests.get("http://web_server:8000/job/" + job_id, timeout=60)
                response.raise_for_status()
                job_status = response.json()['status']
                print('Job status is "%s". (%i seconds passed)' % (job_status, round(time.time() - start_time, 1)))
                if job_status in ['Finished', 'Failed']:
                    break
                time.sleep(5)

            if job_status == 'Finished':
                print('Attempting to download result...')
                filename = 'temp_results.nq.gz'
                with urllib.request.urlopen("http://web_server:8000/job/%s/result/download" % job_id) as response,\
                        open(filename, 'wb') as out_file:
                    shutil.copyfileobj(response, out_file)

                print('Unpacking result...')
                subprocess.run(['gzip', '-df', 'temp_results.nq.gz'])
                if subprocess.run(['md5sum', '-c', '/app/temp_results.nq.md5'], stdout=subprocess.PIPE).returncode == 0:
                    print('Smoke test PASSED at ' + str(datetime.datetime.now()))
                    to_delete['files'].append(filename)
                    to_delete['files'].append('temp_results.nq')
                else:
                    print('MD5 checksum failed. Smoke test FAILED!')
            else:
                print('Smoke test failed!')

        finally:
            print('Reverting changes...')
            try:
                with db_conn() as conn:
                    for table_name in to_delete['timbuctoo_tables'] + renamed['timbuctoo_tables']:
                        print('Dropping view %s.' % (table_name + '_expanded'))
                        with conn.cursor() as cur:
                            cur.execute(psycopg2_sql.SQL('DROP VIEW IF EXISTS {} CASCADE').format(psycopg2_sql.Identifier(table_name + '_expanded')))

                        print('Dropping table %s.' % table_name)
                        with conn.cursor() as cur:
                            cur.execute(psycopg2_sql.SQL('DROP TABLE IF EXISTS {} CASCADE').format(psycopg2_sql.Identifier(table_name)))

                        print('Deleting table entry %s.' % table_name)
                        with conn.cursor() as cur:
                            cur.execute('DELETE FROM timbuctoo_tables WHERE "table_name" = %s', (table_name,))

                    conn.commit()

                    rename(timbuctoo_tables=renamed['timbuctoo_tables'], revert=True)

                    for job_id in to_delete['reconciliation_jobs'] + renamed['reconciliation_jobs']:
                        print('Deleting reconciliation job %s.' % job_id)
                        with conn.cursor() as cur:
                            cur.execute('DELETE FROM reconciliation_jobs WHERE job_id = %s', (job_id,))

                        print('Dropping schema "job_%s"' % job_id)
                        with conn.cursor() as cur:
                            cur.execute(psycopg2_sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(
                                psycopg2_sql.Identifier('job_' + job_id)
                            ))

                    conn.commit()

                    # Always try dropping when renamed?
                    rename(reconciliation_jobs=renamed['reconciliation_jobs'], revert=True)

            except psycopg2.ProgrammingError as e:
                print(e)

            for filename in to_delete['files']:
                print('Deleting file "%s"...' % filename)
                try:
                    os.remove(filename)
                except OSError as e:
                    if e.errno != errno.ENOENT:
                        raise
                    else:
                        print('File "%s" does not exist. Skipping.' % filename)
                else:
                    print('Deleted file "%s".' % filename)
            print('Cleanup complete.')

        sleep_time = 60 * 60
        print('Test done at %s. Going to sleep for %i seconds now.' % (str(datetime.datetime.now()), sleep_time))
        time.sleep(sleep_time)
