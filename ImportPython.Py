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
    'Shift_DTP':'ShiftDowntimePercent',
    'RT_Total':'ShiftRunTimeTotal',
    'RT_Avg':'ShiftRunTimeAvg',
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

def get_shift_data(day_index):
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())  # Get the start of the week (Monday)
    return (start_of_week + timedelta(days=day_index)).date()

# Iterate through the tags and read data from the PLC
def read_shiftdata():
    data = {
        'ShiftIndex': [],
        'DayIndex': [],
        'DateRecorded': datetime.now()
    } # Tuple holds (shift_index, day_index, value)
    try:
        with LogixDriver(PLC_IP) as plc:
            for i in range(2): # Assuming 2 shifts
                for j in range(7): # Assuming 7 days of the week
                    row = {'ShiftIndex': i, 'DayIndex': j}
                    for plc_tag, db_field in tags_to_read.items():
                        tag_name = f'ShiftData[{i},{j}].{plc_tag}'
                        result = plc.read(tag_name)
                        if result and result.value is not None:
                            row[db_field] = result.value
                        else:
                            error_message = result.error if result else "Unknown error"
                            print(f"Failed to read {tag_name} at shift index {i} and day index {j}. Error: {error_message}")
    except Exception as e:
        print(f"Error reading data from PLC: {e}")
    return data

def insert_data_into_postgres(shift_data):
    if not shift_data:
        print("No data to inserted.")
        return
    
    try:
        
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()

        for row in shift_data:
            shift = row.pop('ShiftIndex')
            day = row.pop('DayIndex')

            columns = ['ShiftIndex', 'DayIndex'] + list(row.keys())
            values = [shift, day] + list(row.values())

            placeholders = ', '.join(['%s'] * len(values))
            columns = ', '.join(columns)

            # Prepare the SQL insert statement
            sql = f"INSERT INTO shift_data ({columns}) VALUES ({placeholders})"
            cursor.execute(sql, values)

        conn.commit()
        cursor.close()
        conn.close()
        print("Data inserted successfully into PostgreSQL database.")
    except Exception as e:
        print(f"Error inserting data: {e}")

    if __name__ == "__main__":
        shift_data = read_shiftdata()
        if shift_data:
            insert_data_into_postgres(shift_data)
        else:
            print("No data read from PLC.")
