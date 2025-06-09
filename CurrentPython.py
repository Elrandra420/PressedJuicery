import psycopg2
from pycomm3 import LogixDriver
from datetime import datetime, timedelta

PLC_IP = '192.168.25.186/11'

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
    'ShiftPos':'ShiftID',
    'ShiftTStamp':'ShiftTimeStamp'
} # This is a dictionary

#DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'] # List of days based on 0 = Monday, 6 = Sunday

def get_current_shift_and_day():
    now = datetime.now()
    shift = 0 if now.hour < 18 else 1  # Shifts change at 6am and 6pm
    day_index = now.weekday()  # 0 = Monday, 6 = Sunday
    return shift, day_index

def read_current_shift():
    data = {}
    try:
        with LogixDriver(PLC_IP) as plc:
            shift, day = get_current_shift_and_day()
            data['ShiftIndex'] = shift
            data['DayIndex'] = day
            data['DateRecorded'] = datetime.now()

            for plc_tag, db_field in tags_to_read.items():
                tag_name = plc.read(plc_tag).value
                result = plc.read(tag_name)
                if result and result.value is not None:
                    data[db_field] = result.value
                else:
                    print(f"Failed to read tag {tag_name}: {result.error if result else 'Unknown Error'} from PLC.")
    except Exception as e:
        print(f"Error reading from PLC: {e}")
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

        sql = f"INSERT INTO shift_data ({columns_str}) VALUES ({placeholders})"
        cursor.execute(sql, values)

        conn.commit()
        cursor.close()
        conn.close()

        print("Shift data inserted successfully.")
    except Exception as e:
        print(f"Error inserting data into database: {e}")

if __name__ == "__main__":
    shift_data = read_current_shift()
    if shift_data:
        insert_shift_record(shift_data)
    else:
        print("No data was read from the PLC.")
