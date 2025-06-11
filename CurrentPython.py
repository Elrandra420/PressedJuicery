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

DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'] # List of days based on 0 = Monday, 6 = Sunday
# I eventually want to use this to get the day names, but for now I will just use the day index.

#import logging
# Set up logging
#logging.basicConfig(filename = 'shift_data.log', level = logging.INFO, format = '%(asctime)s - %(levelname)s - %(message)s')
# This script sets up logging to a file named 'shift_data.log' with a specific format that includes the timestamp, log level, and message.

# This function reads the shift text logs
def read_text_logs(shift, day):
    log_entries = []
    try:
        with LogixDriver(PLC_IP) as plc:
            shift_time_tag = f'ShiftData[{shift},{day}].ShiftTStamp'
            shift_time_result = plc.read(shift_time_tag)
            if shift_time_result and shift_time_result.error is None:
                shift_time = shift_time_result.value
            else:
                shift_time = None
                #logging.error(f"Failed to read shift time tag {shift_time_tag}: {shift_time_result.error if shift_time_result else 'Unknown Error'}")
                print(f"Failed to read tag {shift_time_tag}: {shift_time_result.error if shift_time_result else 'Unknown Error'}")
            
            for i in range(30):
                tag = f'ShiftData_Log[{shift}, {day}].Maintenance[{i}]'
                result = plc.read(tag)
                if result and result.value:
                    log_entries.append({
                        'ShiftIndex': shift,
                        'DayIndex': day,
                        'LogType': 'Maintenance',
                        'EntryIndex': i,
                        'LogText': result.value,
                        'ShiftTimeStamp': shift_time
                    })
            for i in range(20):
                tag = f'ShiftData_Log[{shift}, {day}].Process[{i}]'
                result = plc.read(tag)
                if result and result.value:
                    log_entries.append({
                        'ShiftIndex': shift,
                        'DayIndex': day,
                        'LogType': 'Process',
                        'EntryIndex': i,
                        'LogText': result.value,
                        'ShiftTimeStamp': shift_time
                    })
    except Exception as e:
        #logging.error(f"Error reading ShiftData_Logs from PLC for shift {shift}, day {day}: {e}")
        print(f"Error reading ShiftData_Logs from PLC for shift {shift}, day {day}: {e}")
    return log_entries

# This function determines the current shift and day index based on the current time. For use with scheduled tasks.
# Set to save the previous shifts data
def get_current_shift_and_day():
    now = datetime.now()
    if now.hour >= 18 and now.hour < 6:  # Night shift from 6pm to 6am
        shift = 0
        if now.hour < 12:
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

def insert_shift_record(row):
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
                "INSERT INTO ShiftTextLogs (ShiftIndex, DayIndex, LogType, EntryIndex, LogText, ShiftTimeStamp) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (entry['ShiftIndex'], entry['DayIndex'], entry['LogType'], entry['EntryIndex'], entry['LogText'], entry['ShiftTimeStamp'])
            )

        conn.commit()
        cur.close()
        conn.close()

        #logging.info("Shift logs inserted successfully.")
        print("Shift logs inserted successfully.")
    except Exception as e:
        #logging.error(f"Error inserting log entries into database: {e}")
        print(f"Error inserting log entries into database: {e}")

# This is the main entry point of the script. It reads the current shift data and text logs, then inserts them into the PostgreSQL database.
if __name__ == "__main__":
    shift, day = get_current_shift_and_day()
    #shift = 0  # Example shift index, replace with actual logic to determine current shift
    #day = 1    # Example day index, replace with actual logic to determine current day
    shift_data = read_current_shift(shift, day)
    if shift_data:
        insert_shift_record(shift_data)
    else:
        #logging.warning("No shift data was read from the PLC.")
        print("No shift data was read from the PLC.")

    log_data = read_text_logs(shift, day)
    if log_data:
        insert_text_logs(log_data)
    else:
        #logging.warning("No log data was read from the PLC.")
        print("No log data was read from the PLC.")
