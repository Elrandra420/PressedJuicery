# Elijah Andrade
# This script reads production shift data and text logs from a PLC and inserts them into a PostgreSQL database.
import psycopg2
from pycomm3 import LogixDriver
from datetime import datetime, timedelta
# psycopg2 is a PostgreSQL adapter for Python, and pycomm3 is used to communicate with Allen-Bradley PLCs.

# PLC IP address and slot number
PLC_IP = '192.168.25.186/11'

# PostgreSQL database connection parameters
DB_PARAMS = {
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'Controls',
    'host': 'localhost',
    'port': '5432'
} # This dictionary holds the connection parameters for the PostgreSQL database.

# This dictionary contains the Tags to read from the PLC : ShiftData[shift, day].tag_name
# Tags to read: 'tag_name':'database_name'
tags_to_read = {
    'DT_Min':'ShiftDowntimeMinutes',
    'Shift_DTP':'ShiftDowntimePercentage',
    'RT_Total':'ShiftRunTimeTotalMinutes',
    'RT_Avg':'ShiftRuntimeAvg',
    'TotalCycles':'ShiftTotalCycles',
    'TotalPassed':'ShiftTotalPassed',
    'FailedCycles':'ShiftTotalFailed',
    'BottleTotal':'ShiftBottleTotal',
    'Bottle_CycleAvg': 'ShiftBottlesPerCycle',
    'AvgCycleTime':'ShiftCycletimeAvg',
    'Ten_Oz':'ShiftTenOz',
    'Fifteen_Oz':'ShiftFifteenOz',
    'FiftyOne_Oz':'ShiftFiftyOneOz',
    'DownedCount':'ShiftDownedCount',
    'ShiftStart':'ShiftStart',
    'ShiftEnd':'ShiftEnd',
    'Operator':'ShiftOperator',
    'ShiftTStamp':'ShiftTimeStamp'
} # This is a dictionary that maps PLC tags to database fields. Each key is a tag name in the PLC, and each value is the corresponding field name in the PostgreSQL database.

tags_to_read_CycleData = {
    'CycleNum':'CycleNum',
    'CycleTime':'ShiftBottleCount',
    'Passed':'CycleStatus',
    'Shot':'Shot',
    'SKU1':'SKU1',
    'SKU2':'SKU2',
    'SKU1_TOT':'SKU1Total',
    'SKU2_TOT':'SKU2Total',
} # This dictionary maps additional PLC tags related to cycle data to their corresponding database fields.

DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'] # List of days based on 0 = Monday, 6 = Sunday

# This function determines the current shift and day index based on the current time. For use with scheduled tasks.
# Set to save the previous shifts data
def get_current_shift_and_day():
    now = datetime.now()
    if now.hour >= 18 and now.hour < 6:  # Night shift from 6pm to 6am
        shift = 0
        if now.hour < 24:
            day_index = now.weekday()  # 0 = Monday, 6 = Sunday
        else:
            day_index = now.weekday() - 1
            if day_index < 0:  # If it's Monday, set to Sunday
                day_index = 6
        
    elif now.hour >= 6 and now.hour < 18:  # Day shift from 6am to 6pm
        shift = 1
        day_index = now.weekday() - 1
        if day_index < 0:  # If it's Monday, set to Sunday
            day_index = 6
    return shift, day_index

# Uncomment the following lines to enable logging to a file
#import logging

# Set up logging
#logging.basicConfig(filename = 'shift_data.log', level = logging.INFO, format = '%(asctime)s - %(levelname)s - %(message)s')
# This script sets up logging to a file named 'shift_data.log' with a specific format that includes the timestamp, log level, and message.

# This function reads the current shift data from the PLC and returns it as a dictionary.
def read_current_shift(shift, day):
    #shift, day = get_current_shift_and_day()
    data = {
                'ShiftIndex': shift,
                'DayIndex': day,
                'DateRecorded': datetime.now()
            }
    
    try:
        with LogixDriver(PLC_IP) as plc:
            for plc_tag, db_field in tags_to_read.items():
                tag_name = f'ShiftData[{shift},{day}].{plc_tag}'
                result = plc.read(tag_name)
                if result and result.value is not None:
                    data[db_field] = result.value
                    data['ShiftDay'] = DAY_NAMES[day]
                    if db_field == 'ShiftOperator' and str(result.value) == "":
                        #logging.warning(f"Operator field is empty for shift: {shift}, day: {DAY_NAMES[day]}. Please check the PLC configuration.")
                        print(f"Operator field is empty for shift {shift}, day {day}. Please check the PLC configuration.")
                else:
                    #logging.error(f"Failed to read tag {tag_name}: {result.error if result else 'Unknown Error'} from PLC.")
                    print(f"Failed to read tag {tag_name}: {result.error if result else 'Unknown Error'} from PLC.")
    except Exception as e:
        #logging.error(f"Error reading ShiftData from PLC for shift {shift}, day {day}: {e}")
        print(f"Error reading ShiftData from PLC for shift {shift}, day {day}: {e}")

    return data

# This function reads the shift text logs
def read_text_logs(shift, day):
    log_entries = []
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM ProductionShiftData WHERE ShiftIndex = %s AND DayIndex = %s ORDER BY DateRecorded DESC LIMIT 1", (shift, day))
        result = cursor.fetchone()
        conn.close()
        if not result:  
            print(f"No matching ShiftDataID found for shift {shift} and day {day}.")
            return []
        
        shift_data_id = result[0]
    except Exception as e:
        #logging.error(f"Error reading ShiftTextLogs from database: {e}")
        print(f"Database error retrieving ShiftDataID: {e}")
        return []
    
    try:
        with LogixDriver(PLC_IP) as plc:
            for i in range(20):
                text_tag = f'ShiftData_Log[{shift}, {day}].MainLog[{i}]'
                time_tag = f'ShiftData_Log[{shift}, {day}].Main_DT[{i}]'
                ts_tag = f'ShiftData_Log[{shift}, {day}].Main_TSLog[{i}]'

                text_result = plc.read(text_tag)
                if not text_result or not text_result.value or text_result.value.strip() == "":
                    print(f"Text result for tag {text_tag} in EntryIndex{i} is None or empty.")
                    continue # Skip to the next iteration if field is Blank
                time_result = plc.read(time_tag)
                ts_result = plc.read(ts_tag)

                if text_result and text_result.value is not None:
                    log_entry = {
                        'ShiftDataID': shift_data_id,
                        'LogType': 'Maintenance',
                        'EntryIndex': i,
                        'LogText': text_result.value if text_result and text_result.value is not None else None,
                        'LogTStamp': ts_result.value if ts_result and ts_result.value is not None else None,
                        'LogTime': time_result.value if time_result and time_result.value is not None else None
                    }
                    log_entries.append(log_entry)
                else :
                    print(f"Text result for tag {text_tag} in EntryIndex{i} is None or empty.")
            for j in range(30):
                text_tagPro = f'ShiftData_Log[{shift}, {day}].ProLog[{j}]'
                time_tagPro = f'ShiftData_Log[{shift}, {day}].Pro_DT[{j}]'
                ts_tagPro = f'ShiftData_Log[{shift}, {day}].Pro_TSLog[{j}]'

                text_Pro_result = plc.read(text_tagPro)
                if not text_Pro_result or not text_Pro_result.value or text_Pro_result.value.strip() == "":
                    print(f"Text result for tag {text_tagPro} in EntryIndex{j} is None or empty.")
                    continue
                time_Pro_result = plc.read(time_tagPro)
                ts_Pro_result = plc.read(ts_tagPro)
                if text_Pro_result and text_Pro_result.value is not None:
                    log_entry = {
                        'ShiftDataID': shift_data_id,
                        'LogType': 'Process',
                        'EntryIndex': j,
                        'LogText': text_Pro_result.value if text_Pro_result and text_Pro_result.value is not None else None,
                        'LogTStamp': ts_Pro_result.value if ts_Pro_result and ts_Pro_result.value is not None else None,
                        'LogTime': time_Pro_result.value if time_Pro_result and time_Pro_result.value is not None else None
                    }
                    log_entries.append(log_entry)
    except Exception as e:
        #logging.error(f"Error reading ShiftData_Logs from PLC for shift {shift}, day {day}: {e}")
        print(f"Error reading ShiftData_Logs from PLC for shift {shift}, day {day}: {e}")
    return log_entries

def read_cycle_data(shift, day):
    cycle_data = []
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM ProductionShiftData WHERE ShiftIndex = %s AND DayIndex = %s ORDER BY DateRecorded DESC LIMIT 1", (shift, day))
        result = cursor.fetchone()
        conn.close()
        if not result:  
            print(f"No matching ShiftDataID found for shift {shift} and day {day}.")
            return []
        
        Cycleshift_data_id = result[0]
    except Exception as e:
        #logging.error(f"Error reading ShiftDataID for CycleData from database: {e}")
        print(f"Database error retrieving ShiftDataID: {e}")
        return []

    try:
        with LogixDriver(PLC_IP) as plc:
            for x in range(120):  # Assuming a maximum of 120 cycles
                prefix = f'ShiftCycle[{shift}, {day}].CycleData[{x}]'
                cycle_num_result = plc.read(f'{prefix}.CycleNum')
                if not cycle_num_result or cycle_num_result.value in [None, '']:
                    print(f"CycleNum at index {x} is None or empty. Skipping.")
                    continue  # Skip to the next iteration if field is Blank

                # Read other cycle data tags
                cycle_time = plc.read(f'{prefix}.CycleTime')
                passed = plc.read(f'{prefix}.Passed')
                shot = plc.read(f'{prefix}.Shot')
                sku1 = plc.read(f'{prefix}.SKU1')
                sku2 = plc.read(f'{prefix}.SKU2')
                sku1_tot = plc.read(f'{prefix}.SKU1_TOT')
                sku2_tot = plc.read(f'{prefix}.SKU2_TOT')

                cycle_data_entry = {
                    'ShiftDataID': Cycleshift_data_id,
                    'CycleIndex': x,
                    'CycleNumber': cycle_num_result.value,
                    'CycleTime': cycle_time.value if cycle_time else None,
                    'Passed': 'Passed' if passed and passed.value == 1 else 'Failed' if passed and passed.value == 0 else None,
                    'Shot': shot.value if shot else None,
                    'SKU1': sku1.value if sku1 else None,
                    'SKU2': sku2.value if sku2 else None,
                    'SKU1Total': sku1_tot.value if sku1_tot else None,
                    'SKU2Total': sku2_tot.value if sku2_tot else None
                }
                cycle_data.append(cycle_data_entry)
    except Exception as e:
        #logging.error(f"Error reading CycleData from PLC for shift {shift}, day {day}: {e}")
        print(f"Error reading CycleData from PLC for shift {shift}, day {day}: {e}")

    return cycle_data

def insert_shift_data(row):
    if not row:
        #logging.warning("No data to insert into the database.")
        print("No data to insert.")
        return
    
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()

        columns = list(row.keys())
        values = list(row.values())

        placeholders = ', '.join(['%s'] * len(values))
        columns_str = ', '.join(columns)
        
        sql = f"INSERT INTO ProductionShiftData ({columns_str}) VALUES ({placeholders})"
        cursor.execute(sql, values)

        conn.commit()
        cursor.close()
        conn.close()

        #logging.info("Shift data inserted successfully.")
        print("Shift data inserted successfully.")
    except Exception as e:
        #logging.error(f"Error inserting shift data into database: {e}")
        print(f"Error inserting shift data into database: {e}")

def insert_text_logs(log_entries):
    if not log_entries:
        #logging.warning("No log entries to insert into the database.")
        print("No log entries to insert.")
        return
    
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        for entry in log_entries:
            cur.execute(
                "INSERT INTO ShiftTextLogs (ShiftDataID, LogType, EntryIndex, LogText, LogTStamp, LogTime) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (entry['ShiftDataID'], entry['LogType'], entry['EntryIndex'], entry['LogText'], entry['LogTStamp'], entry['LogTime'])
            )

        conn.commit()
        cur.close()
        conn.close()

        #logging.info("Shift logs inserted successfully.")
        print("Shift logs inserted successfully.")
    except Exception as e:
        #logging.error(f"Error inserting log entries into database: {e}")
        print(f"Error inserting log entries into database: {e}")

def insert_cycle_data(cycle_data):
    if not cycle_data:
        #logging.warning("No cycle data to insert into the database.")
        print("No cycle data to insert.")
        return
    
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()

        for entry in cycle_data:
            cursor.execute(
                "INSERT INTO ProductionCycleData (ShiftDataID, CycleIndex, CycleNumber, CycleTime, CycleStatus, Shot, SKU1, SKU2, SKU1_Total, SKU2_Total) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (entry['ShiftDataID'], entry['CycleIndex'], entry['CycleNumber'], entry['CycleTime'], entry['CycleStatus'], entry['Shot'], entry['SKU1'], entry['SKU2'], entry['SKU1_Total'], entry['SKU2_Total'])
            )

        conn.commit()
        cursor.close()
        conn.close()

        #logging.info("Cycle data inserted successfully.")
        print("Cycle data inserted successfully.")
    except Exception as e:
        #logging.error(f"Error inserting cycle data into database: {e}")
        print(f"Error inserting cycle data into database: {e}")

# This is the main entry point of the script. It reads the current shift data and text logs, then inserts them into the PostgreSQL database.
if __name__ == "__main__":
    shift, day = get_current_shift_and_day()
    #shift = 1  # Example shift index, replace with actual logic to determine current shift
    #day = 2    # Example day index, replace with actual logic to determine current day

    shift_data = read_current_shift(shift, day)
    if shift_data:
        insert_shift_data(shift_data)
    else:
    #    #logging.warning("No shift data was read from the PLC.")
        print("No shift data was read from the PLC.")

    log_data = read_text_logs(shift, day)
    if log_data:
        insert_text_logs(log_data)
    else:
    #    #logging.warning("No log data was read from the PLC.")
        print("No log data was read from the PLC.")

    cycle_data = read_cycle_data(shift, day)
    if cycle_data:
        insert_cycle_data(cycle_data)
    else:
        #logging.warning("No cycle data was read from the PLC.")
        print("No cycle data was read from the PLC.")
