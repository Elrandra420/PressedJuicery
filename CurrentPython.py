import psycopg2
from pycomm3 import LogixDriver
from datetime import datetime, timedelta

# PLC IP address and slot number
PLC_IP = '192.168.25.186/11'

# PostgreSQL database connection parameters
DB_PARAMS = {
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'Controls',
    'host': 'localhost',
    'port': '5432'
}

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
} # This is a dictionary

#DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'] # List of days based on 0 = Monday, 6 = Sunday

def read_text_logs(shift, day):
    log_entries = []
    try:
        with LogixDriver(PLC_IP) as plc:
            shift_time_tag = f'ShiftData[{shift},{day}].ShiftTStamp'
            shift_time_result = plc.read(shift_time_tag)
            shift_time = shift_time_result.value if shift_time_result else None
            
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
                tag = f'ShiftData_Log[{shift},{day}].Process[{i}]'
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
        print(f"Error reading ShiftData_Logs from PLC: {e}")
    return log_entries

# This function determines the current shift and day index based on the current time. For use with scheduled tasks.
def get_current_shift_and_day():
    now = datetime.now()
    shift = 1 # if now.hour < 18 else 1  # Shifts change at 6am and 6pm
    day_index = 0 #now.weekday()  # 0 = Monday, 6 = Sunday
    return shift, day_index

def read_current_shift():
    shift, day = get_current_shift_and_day()
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
                else:
                    print(f"Failed to read tag {tag_name}: {result.error if result else 'Unknown Error'} from PLC.")
    except Exception as e:
        print(f"Error reading ShiftData from PLC: {e}")
    return data
    
def insert_shift_record(row):
    if not row:
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

        print("Shift data inserted successfully.")
    except Exception as e:
        print(f"Error inserting data into database: {e}")

def insert_text_logs(log_entries):
    if not log_entries:
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

        print("Shift logs inserted successfully.")
    except Exception as e:
        print(f"Error inserting logs into database: {e}")

if __name__ == "__main__":
    shift, day = get_current_shift_and_day()

    shift_data = read_current_shift()
    if shift_data:
        insert_shift_record(shift_data)
    else:
        print("No shift data was read from the PLC.")

    log_data = read_text_logs(shift, day)
    if log_data:
        insert_text_logs(log_data)
    else:
        print("No log data was read from the PLC.")
