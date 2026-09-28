import streamlit as st
st.image("malibu1234.jpg")
import mysql.connector
from mysql.connector import Error, IntegrityError
from datetime import datetime, date
import pandas as pd
from openai import OpenAI

# ============================================================
# CẤU HÌNH
# ============================================================

st.set_page_config(
    page_title="Khách sạn Malibu",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# MYSQL AIVEN
# ============================================================
# Thông tin kết nối theo yêu cầu.
# Nếu database trên Aiven của bạn có tên khác "defaultdb",
# hãy đổi DB_NAME bên dưới.

DB_USER = "avnadmin"
DB_PASSWORD = "AVNS_TX2oBXmTGGjXba6p7j1"
DB_HOST = "mysql-3a5ef2bc-binhquytoc.a.aivencloud.com"
DB_PORT = 14483
DB_NAME = "defaultdb"

# OpenAI API key: ưu tiên Streamlit Secrets, nếu chưa có thì
# người dùng có thể nhập trực tiếp trong sidebar.
OPENAI_MODEL = "gpt-5.6-luna"

# Aiven MySQL yêu cầu kết nối SSL.
# Cấu hình này mã hóa kết nối nhưng không bắt buộc kiểm tra CA.
DB_SSL_CONFIG = {
    "ssl_disabled": False,
    "ssl_verify_cert": False,
    "ssl_verify_identity": False,
}


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    """Tạo kết nối tới MySQL Aiven."""
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        connection_timeout=15,
        autocommit=False,
        **DB_SSL_CONFIG
    )


def init_database():
    """Tạo database/table nếu chưa tồn tại."""
    conn = None
    cursor = None

    try:
        # Kết nối không chỉ định database trước để có thể tạo DB.
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            connection_timeout=15,
            **DB_SSL_CONFIG
        )
        cursor = conn.cursor()

        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        conn.commit()
        cursor.close()
        conn.close()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rooms (
                id INT AUTO_INCREMENT PRIMARY KEY,
                room_number VARCHAR(20) NOT NULL UNIQUE,
                room_type VARCHAR(50) NOT NULL,
                floor INT NOT NULL,
                price DECIMAL(15,2) NOT NULL DEFAULT 0,
                status VARCHAR(30) NOT NULL DEFAULT 'Trống',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
              DEFAULT CHARSET=utf8mb4
              COLLATE=utf8mb4_unicode_ci
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(150) NOT NULL,
                phone VARCHAR(30),
                email VARCHAR(150),
                id_number VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_guest_name (full_name),
                INDEX idx_guest_phone (phone)
            ) ENGINE=InnoDB
              DEFAULT CHARSET=utf8mb4
              COLLATE=utf8mb4_unicode_ci
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                guest_id INT NOT NULL,
                room_id INT NOT NULL,
                check_in DATE NOT NULL,
                check_out DATE NOT NULL,
                adults INT NOT NULL DEFAULT 1,
                children INT NOT NULL DEFAULT 0,
                status VARCHAR(30) NOT NULL DEFAULT 'Đã đặt',
                total_amount DECIMAL(15,2) NOT NULL DEFAULT 0,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_bookings_guest
                    FOREIGN KEY (guest_id)
                    REFERENCES guests(id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT,

                CONSTRAINT fk_bookings_room
                    FOREIGN KEY (room_id)
                    REFERENCES rooms(id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT,

                INDEX idx_booking_room (room_id),
                INDEX idx_booking_dates (check_in, check_out),
                INDEX idx_booking_status (status)
            ) ENGINE=InnoDB
              DEFAULT CHARSET=utf8mb4
              COLLATE=utf8mb4_unicode_ci
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INT AUTO_INCREMENT PRIMARY KEY,
                booking_id INT NOT NULL,
                amount DECIMAL(15,2) NOT NULL,
                payment_method VARCHAR(50) NOT NULL DEFAULT 'Tiền mặt',
                payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                note TEXT,

                CONSTRAINT fk_payments_booking
                    FOREIGN KEY (booking_id)
                    REFERENCES bookings(id)
                    ON UPDATE CASCADE
                    ON DELETE RESTRICT,

                INDEX idx_payment_booking (booking_id)
            ) ENGINE=InnoDB
              DEFAULT CHARSET=utf8mb4
              COLLATE=utf8mb4_unicode_ci
        """)

        # Tạo dữ liệu phòng mẫu nếu chưa có phòng.
        cursor.execute("SELECT COUNT(*) FROM rooms")
        count = cursor.fetchone()[0]

        if count == 0:
            sample_rooms = [
                ("101", "Deluxe", 1, 1800000, "Trống"),
                ("102", "Deluxe", 1, 1800000, "Trống"),
                ("103", "Deluxe", 1, 1800000, "Trống"),
                ("104", "Superior", 1, 1500000, "Trống"),
                ("201", "Deluxe", 2, 2000000, "Trống"),
                ("202", "Deluxe", 2, 2000000, "Trống"),
                ("203", "Suite", 2, 3500000, "Trống"),
                ("204", "Suite", 2, 3500000, "Trống"),
                ("301", "Deluxe", 3, 2200000, "Trống"),
                ("302", "Deluxe", 3, 2200000, "Trống"),
                ("303", "Suite", 3, 4000000, "Trống"),
                ("304", "VIP", 3, 5500000, "Trống"),
            ]

            cursor.executemany("""
                INSERT INTO rooms
                    (room_number, room_type, floor, price, status)
                VALUES (%s, %s, %s, %s, %s)
            """, sample_rooms)

        conn.commit()

    except Error as e:
        if conn:
            conn.rollback()
        st.error(
            "Không thể kết nối hoặc khởi tạo MySQL Aiven.\n\n"
            f"Chi tiết lỗi: {e}"
        )
        st.stop()

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


# ============================================================
# HÀM DATABASE
# ============================================================

def fetch_rooms():
    conn = None
    try:
        conn = get_connection()
        query = """
            SELECT
                id,
                room_number,
                room_type,
                floor,
                price,
                status,
                created_at,
                updated_at
            FROM rooms
            ORDER BY floor, room_number
        """
        return pd.read_sql(query, conn)
    finally:
        if conn and conn.is_connected():
            conn.close()


def fetch_bookings():
    conn = None
    try:
        conn = get_connection()

        query = """
            SELECT
                b.id,
                g.full_name,
                g.phone,
                g.email,
                g.id_number,
                r.room_number,
                r.room_type,
                b.check_in,
                b.check_out,
                b.adults,
                b.children,
                b.status,
                b.total_amount,
                COALESCE(
                    (
                        SELECT SUM(p.amount)
                        FROM payments p
                        WHERE p.booking_id = b.id
                    ),
                    0
                ) AS paid_amount,
                b.note,
                b.created_at
            FROM bookings b
            INNER JOIN guests g ON b.guest_id = g.id
            INNER JOIN rooms r ON b.room_id = r.id
            ORDER BY b.id DESC
        """

        return pd.read_sql(query, conn)

    finally:
        if conn and conn.is_connected():
            conn.close()


def fetch_payments(booking_id=None):
    conn = None
    try:
        conn = get_connection()

        if booking_id is None:
            query = """
                SELECT
                    p.id,
                    p.booking_id,
                    g.full_name,
                    r.room_number,
                    p.amount,
                    p.payment_method,
                    p.payment_date,
                    p.note
                FROM payments p
                INNER JOIN bookings b ON p.booking_id = b.id
                INNER JOIN guests g ON b.guest_id = g.id
                INNER JOIN rooms r ON b.room_id = r.id
                ORDER BY p.id DESC
            """
            return pd.read_sql(query, conn)

        query = """
            SELECT
                p.id,
                p.booking_id,
                p.amount,
                p.payment_method,
                p.payment_date,
                p.note
            FROM payments p
            WHERE p.booking_id = %s
            ORDER BY p.id DESC
        """
        return pd.read_sql(query, conn, params=[booking_id])

    finally:
        if conn and conn.is_connected():
            conn.close()


def add_room(room_number, room_type, floor, price):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO rooms
                (room_number, room_type, floor, price, status)
            VALUES (%s, %s, %s, %s, 'Trống')
        """, (room_number, room_type, floor, price))

        conn.commit()
        return True, "Thêm phòng thành công."

    except IntegrityError:
        if conn:
            conn.rollback()
        return False, "Số phòng đã tồn tại."

    except Error as e:
        if conn:
            conn.rollback()
        return False, f"Lỗi database: {e}"

    finally:
        if conn and conn.is_connected():
            conn.close()


def update_room(room_id, room_number, room_type, floor, price, status):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE rooms
            SET
                room_number = %s,
                room_type = %s,
                floor = %s,
                price = %s,
                status = %s
            WHERE id = %s
        """, (
            room_number,
            room_type,
            floor,
            price,
            status,
            room_id
        ))

        conn.commit()
        return True, "Cập nhật phòng thành công."

    except IntegrityError:
        if conn:
            conn.rollback()
        return False, "Số phòng đã tồn tại."

    except Error as e:
        if conn:
            conn.rollback()
        return False, f"Lỗi database: {e}"

    finally:
        if conn and conn.is_connected():
            conn.close()


def delete_room(room_id):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM bookings WHERE room_id = %s",
            (room_id,)
        )
        booking_count = cursor.fetchone()[0]

        if booking_count > 0:
            return (
                False,
                "Không thể xóa phòng vì phòng đã có lịch sử đặt."
            )

        cursor.execute(
            "DELETE FROM rooms WHERE id = %s",
            (room_id,)
        )

        conn.commit()
        return True, "Đã xóa phòng."

    except Error as e:
        if conn:
            conn.rollback()
        return False, f"Lỗi database: {e}"

    finally:
        if conn and conn.is_connected():
            conn.close()


def room_has_conflicting_booking(room_id, check_in, check_out):
    """
    Kiểm tra phòng có booking đang trùng thời gian hay không.
    Không tính booking đã hủy hoặc đã trả phòng.
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*)
            FROM bookings
            WHERE room_id = %s
              AND status NOT IN ('Hủy', 'Đã trả phòng')
              AND check_in < %s
              AND check_out > %s
        """, (
            room_id,
            check_out.isoformat(),
            check_in.isoformat()
        ))

        return cursor.fetchone()[0] > 0

    finally:
        if conn and conn.is_connected():
            conn.close()


def create_booking(
    full_name,
    phone,
    email,
    id_number,
    room_id,
    check_in,
    check_out,
    adults,
    children,
    note
):
    conn = None

    try:
        if check_out <= check_in:
            raise ValueError(
                "Ngày trả phòng phải sau ngày nhận phòng."
            )

        if room_has_conflicting_booking(
            room_id,
            check_in,
            check_out
        ):
            raise ValueError(
                "Phòng đã có booking trùng thời gian."
            )

        conn = get_connection()
        cursor = conn.cursor()

        # Lấy thông tin phòng và khóa dòng để hạn chế
        # trường hợp hai người đặt cùng một phòng.
        cursor.execute("""
            SELECT id, price, status
            FROM rooms
            WHERE id = %s
            FOR UPDATE
        """, (room_id,))

        room = cursor.fetchone()

        if not room:
            raise ValueError("Không tìm thấy phòng.")

        price = float(room[1])
        nights = (check_out - check_in).days

        if nights <= 0:
            raise ValueError(
                "Ngày trả phòng phải sau ngày nhận phòng."
            )

        total = nights * price

        # Tìm khách theo CCCD/Passport hoặc số điện thoại.
        guest_id = None

        if id_number.strip():
            cursor.execute("""
                SELECT id
                FROM guests
                WHERE id_number = %s
                LIMIT 1
            """, (id_number.strip(),))
            guest = cursor.fetchone()

            if guest:
                guest_id = guest[0]

        if guest_id is None and phone.strip():
            cursor.execute("""
                SELECT id
                FROM guests
                WHERE phone = %s
                LIMIT 1
            """, (phone.strip(),))
            guest = cursor.fetchone()

            if guest:
                guest_id = guest[0]

        if guest_id:
            cursor.execute("""
                UPDATE guests
                SET
                    full_name = %s,
                    phone = %s,
                    email = %s,
                    id_number = %s
                WHERE id = %s
            """, (
                full_name.strip(),
                phone.strip(),
                email.strip(),
                id_number.strip(),
                guest_id
            ))
        else:
            cursor.execute("""
                INSERT INTO guests
                    (full_name, phone, email, id_number)
                VALUES (%s, %s, %s, %s)
            """, (
                full_name.strip(),
                phone.strip(),
                email.strip(),
                id_number.strip()
            ))
            guest_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO bookings
                (
                    guest_id,
                    room_id,
                    check_in,
                    check_out,
                    adults,
                    children,
                    status,
                    total_amount,
                    note
                )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            guest_id,
            room_id,
            check_in.isoformat(),
            check_out.isoformat(),
            adults,
            children,
            "Đã đặt",
            total,
            note.strip()
        ))

        cursor.execute("""
            UPDATE rooms
            SET status = 'Đã đặt'
            WHERE id = %s
        """, (room_id,))

        conn.commit()

        return (
            True,
            f"Đặt phòng thành công. Tổng tiền: "
            f"{total:,.0f} VNĐ"
        )

    except ValueError as e:
        if conn:
            conn.rollback()
        return False, str(e)

    except Error as e:
        if conn:
            conn.rollback()
        return False, f"Lỗi database: {e}"

    finally:
        if conn and conn.is_connected():
            conn.close()


def update_booking_status(booking_id, new_status):
    conn = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT room_id
            FROM bookings
            WHERE id = %s
        """, (booking_id,))

        booking = cursor.fetchone()

        if not booking:
            return False, "Không tìm thấy booking."

        room_id = booking[0]

        cursor.execute("""
            UPDATE bookings
            SET status = %s
            WHERE id = %s
        """, (new_status, booking_id))

        status_mapping = {
            "Đã đặt": "Đã đặt",
            "Đang ở": "Đang ở",
            "Đã trả phòng": "Đang dọn",
            "Hủy": "Trống"
        }

        room_status = status_mapping.get(
            new_status,
            "Trống"
        )

        cursor.execute("""
            UPDATE rooms
            SET status = %s
            WHERE id = %s
        """, (room_status, room_id))

        conn.commit()
        return True, "Đã cập nhật trạng thái."

    except Error as e:
        if conn:
            conn.rollback()
        return False, f"Lỗi database: {e}"

    finally:
        if conn and conn.is_connected():
            conn.close()


def make_payment(booking_id, amount, method, note):
    conn = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT total_amount
            FROM bookings
            WHERE id = %s
        """, (booking_id,))

        booking = cursor.fetchone()

        if not booking:
            return False, "Không tìm thấy booking."

        total_amount = float(booking[0])

        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0)
            FROM payments
            WHERE booking_id = %s
        """, (booking_id,))

        paid_amount = float(cursor.fetchone()[0])
        remaining = total_amount - paid_amount

        if amount <= 0:
            return False, "Số tiền phải lớn hơn 0."

        if amount > remaining:
            return (
                False,
                f"Số tiền thanh toán vượt quá công nợ. "
                f"Còn lại: {remaining:,.0f} VNĐ"
            )

        cursor.execute("""
            INSERT INTO payments
                (booking_id, amount, payment_method, note)
            VALUES (%s, %s, %s, %s)
        """, (
            booking_id,
            amount,
            method,
            note.strip()
        ))

        conn.commit()
        return True, "Thanh toán đã được ghi nhận."

    except Error as e:
        if conn:
            conn.rollback()
        return False, f"Lỗi database: {e}"

    finally:
        if conn and conn.is_connected():
            conn.close()


# ============================================================
# HÀM HIỂN THỊ
# ============================================================

def format_money(value):
    if pd.isna(value):
        value = 0
    return f"{float(value):,.0f} VNĐ"


def status_color(status):
    mapping = {
        "Trống": "🟢",
        "Đã đặt": "🟡",
        "Đang ở": "🔵",
        "Đang dọn": "🟠",
        "Bảo trì": "🔴"
    }

    return mapping.get(status, "⚪")


# ============================================================
# KHỞI TẠO DATABASE
# ============================================================

init_database()


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🏨 HOTEL MANAGER")
st.sidebar.caption("Hệ thống quản lý khách sạn")

menu = st.sidebar.radio(
    "MENU",
    [
        "📊 Tổng quan",
        "🛏️ Quản lý phòng",
        "📅 Đặt phòng",
        "👤 Khách lưu trú",
        "💳 Thanh toán"
    ]
)

st.sidebar.divider()

st.sidebar.success(
    "🟢 Đã cấu hình MySQL Aiven"
)

st.sidebar.info(
    "Phần mềm quản lý khách sạn "
    "được xây dựng bằng Streamlit + MySQL Aiven."
)


# ============================================================
# TỔNG QUAN
# ============================================================

if menu == "📊 Tổng quan":

    st.title("📊 Tổng quan khách sạn")
    st.caption(
        f"Cập nhật: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    rooms = fetch_rooms()
    bookings = fetch_bookings()

    total_rooms = len(rooms)

    empty_rooms = len(
        rooms[rooms["status"] == "Trống"]
    )

    reserved_rooms = len(
        rooms[rooms["status"] == "Đã đặt"]
    )

    occupied_rooms = len(
        rooms[rooms["status"] == "Đang ở"]
    )

    cleaning_rooms = len(
        rooms[rooms["status"] == "Đang dọn"]
    )

    maintenance_rooms = len(
        rooms[rooms["status"] == "Bảo trì"]
    )

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    col1.metric("Tổng phòng", total_rooms)
    col2.metric("🟢 Trống", empty_rooms)
    col3.metric("🟡 Đã đặt", reserved_rooms)
    col4.metric("🔵 Đang ở", occupied_rooms)
    col5.metric("🟠 Đang dọn", cleaning_rooms)
    col6.metric("🔴 Bảo trì", maintenance_rooms)

    st.divider()

    st.subheader("🏨 Sơ đồ phòng")

    if not rooms.empty:

        floors = sorted(
            rooms["floor"].dropna().unique()
        )

        for floor in floors:

            st.markdown(f"### Tầng {int(floor)}")

            floor_rooms = rooms[
                rooms["floor"] == floor
            ]

            columns = st.columns(4)

            for index, (_, room) in enumerate(
                floor_rooms.iterrows()
            ):

                with columns[index % 4]:

                    st.markdown(
                        f"""
                        <div style="
                            border:1px solid #ddd;
                            border-radius:10px;
                            padding:15px;
                            margin-bottom:10px;
                            background:#fafafa;
                        ">
                            <h3>🚪 {room['room_number']}</h3>
                            <p>{room['room_type']}</p>
                            <p>{status_color(room['status'])}
                            <b>{room['status']}</b></p>
                            <p>{format_money(room['price'])}/đêm</p>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

    st.divider()

    st.subheader("📅 Đặt phòng gần đây")

    if bookings.empty:
        st.info("Chưa có dữ liệu đặt phòng.")
    else:
        recent = bookings.head(10).copy()

        st.dataframe(
            recent[
                [
                    "id",
                    "full_name",
                    "room_number",
                    "check_in",
                    "check_out",
                    "status",
                    "total_amount",
                    "paid_amount"
                ]
            ],
            column_config={
                "id": "Booking ID",
                "full_name": "Khách hàng",
                "room_number": "Phòng",
                "check_in": "Ngày nhận",
                "check_out": "Ngày trả",
                "status": "Trạng thái",
                "total_amount": st.column_config.NumberColumn(
                    "Tổng tiền",
                    format="%,.0f VNĐ"
                ),
                "paid_amount": st.column_config.NumberColumn(
                    "Đã thanh toán",
                    format="%,.0f VNĐ"
                )
            },
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# QUẢN LÝ PHÒNG
# ============================================================

elif menu == "🛏️ Quản lý phòng":

    st.title("🛏️ Quản lý phòng")

    tab1, tab2, tab3 = st.tabs(
        [
            "Danh sách phòng",
            "Thêm phòng",
            "Chỉnh sửa phòng"
        ]
    )

    rooms = fetch_rooms()

    # --------------------------------------------------------
    # DANH SÁCH
    # --------------------------------------------------------

    with tab1:

        col1, col2 = st.columns(2)

        with col1:
            search = st.text_input(
                "🔎 Tìm số phòng",
                placeholder="Ví dụ: 101"
            )

        with col2:
            status_filter = st.selectbox(
                "Lọc trạng thái",
                [
                    "Tất cả",
                    "Trống",
                    "Đã đặt",
                    "Đang ở",
                    "Đang dọn",
                    "Bảo trì"
                ]
            )

        filtered = rooms.copy()

        if search:
            filtered = filtered[
                filtered["room_number"]
                .astype(str)
                .str.contains(
                    search,
                    case=False,
                    na=False
                )
            ]

        if status_filter != "Tất cả":
            filtered = filtered[
                filtered["status"] == status_filter
            ]

        st.dataframe(
            filtered[
                [
                    "id",
                    "room_number",
                    "room_type",
                    "floor",
                    "price",
                    "status"
                ]
            ],
            column_config={
                "id": "ID",
                "room_number": "Số phòng",
                "room_type": "Loại phòng",
                "floor": "Tầng",
                "price": st.column_config.NumberColumn(
                    "Giá/đêm",
                    format="%,.0f VNĐ"
                ),
                "status": "Trạng thái"
            },
            use_container_width=True,
            hide_index=True
        )

    # --------------------------------------------------------
    # THÊM PHÒNG
    # --------------------------------------------------------

    with tab2:

        st.subheader("➕ Thêm phòng mới")

        with st.form("add_room_form"):

            col1, col2 = st.columns(2)

            with col1:

                room_number = st.text_input(
                    "Số phòng *"
                )

                room_type = st.selectbox(
                    "Loại phòng",
                    [
                        "Standard",
                        "Superior",
                        "Deluxe",
                        "Suite",
                        "VIP"
                    ]
                )

            with col2:

                floor = st.number_input(
                    "Tầng",
                    min_value=1,
                    max_value=100,
                    value=1
                )

                price = st.number_input(
                    "Giá phòng/đêm (VNĐ)",
                    min_value=0,
                    value=1500000,
                    step=100000
                )

            submit = st.form_submit_button(
                "➕ Thêm phòng",
                use_container_width=True
            )

            if submit:

                if not room_number.strip():
                    st.error(
                        "Vui lòng nhập số phòng."
                    )
                else:

                    success, message = add_room(
                        room_number.strip(),
                        room_type,
                        floor,
                        price
                    )

                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

    # --------------------------------------------------------
    # CHỈNH SỬA
    # --------------------------------------------------------

    with tab3:

        st.subheader("✏️ Chỉnh sửa phòng")

        if rooms.empty:
            st.info("Chưa có phòng.")
        else:

            room_options = {
                f"{row['room_number']} - "
                f"{row['room_type']}":
                row["id"]
                for _, row in rooms.iterrows()
            }

            selected_room = st.selectbox(
                "Chọn phòng",
                list(room_options.keys())
            )

            selected_id = room_options[selected_room]

            room = rooms[
                rooms["id"] == selected_id
            ].iloc[0]

            with st.form("edit_room_form"):

                col1, col2 = st.columns(2)

                with col1:

                    edit_number = st.text_input(
                        "Số phòng",
                        value=str(room["room_number"])
                    )

                    room_types = [
                        "Standard",
                        "Superior",
                        "Deluxe",
                        "Suite",
                        "VIP"
                    ]

                    current_type = room["room_type"]

                    edit_type = st.selectbox(
                        "Loại phòng",
                        room_types,
                        index=(
                            room_types.index(current_type)
                            if current_type in room_types
                            else 0
                        )
                    )

                    edit_floor = st.number_input(
                        "Tầng",
                        min_value=1,
                        max_value=100,
                        value=int(room["floor"])
                    )

                with col2:

                    edit_price = st.number_input(
                        "Giá phòng/đêm",
                        min_value=0.0,
                        value=float(room["price"]),
                        step=100000.0
                    )

                    statuses = [
                        "Trống",
                        "Đã đặt",
                        "Đang ở",
                        "Đang dọn",
                        "Bảo trì"
                    ]

                    edit_status = st.selectbox(
                        "Trạng thái",
                        statuses,
                        index=(
                            statuses.index(room["status"])
                            if room["status"] in statuses
                            else 0
                        )
                    )

                col_save, col_delete = st.columns(2)

                with col_save:
                    save = st.form_submit_button(
                        "💾 Lưu thay đổi",
                        use_container_width=True
                    )

                with col_delete:
                    delete = st.form_submit_button(
                        "🗑️ Xóa phòng",
                        use_container_width=True
                    )

                if save:

                    if not edit_number.strip():
                        st.error(
                            "Số phòng không được để trống."
                        )
                    else:
                        success, message = update_room(
                            selected_id,
                            edit_number.strip(),
                            edit_type,
                            edit_floor,
                            edit_price,
                            edit_status
                        )

                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)

                if delete:

                    success, message = delete_room(
                        selected_id
                    )

                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)


# ============================================================
# ĐẶT PHÒNG
# ============================================================

elif menu == "📅 Đặt phòng":

    st.title("📅 Đặt phòng")

    rooms = fetch_rooms()

    available_rooms = rooms[
        rooms["status"] == "Trống"
    ]

    if available_rooms.empty:

        st.warning(
            "Hiện tại không có phòng trống."
        )

    else:

        st.subheader("Thông tin khách")

        with st.form("booking_form"):

            col1, col2 = st.columns(2)

            with col1:

                full_name = st.text_input(
                    "Họ và tên khách *"
                )

                phone = st.text_input(
                    "Số điện thoại"
                )

                email = st.text_input(
                    "Email"
                )

                id_number = st.text_input(
                    "CCCD / Passport"
                )

            with col2:

                room_options = {
                    f"Phòng {row['room_number']} - "
                    f"{row['room_type']} - "
                    f"{format_money(row['price'])}/đêm":
                    row["id"]
                    for _, row in available_rooms.iterrows()
                }

                selected_room = st.selectbox(
                    "Chọn phòng *",
                    list(room_options.keys())
                )

                room_id = room_options[selected_room]

                check_in = st.date_input(
                    "Ngày nhận phòng",
                    value=date.today()
                )

                check_out = st.date_input(
                    "Ngày trả phòng",
                    value=date.today()
                )

                adults = st.number_input(
                    "Số người lớn",
                    min_value=1,
                    max_value=20,
                    value=1
                )

                children = st.number_input(
                    "Số trẻ em",
                    min_value=0,
                    max_value=20,
                    value=0
                )

            note = st.text_area(
                "Ghi chú"
            )

            submit_booking = st.form_submit_button(
                "📅 Xác nhận đặt phòng",
                use_container_width=True
            )

            if submit_booking:

                if not full_name.strip():
                    st.error(
                        "Vui lòng nhập họ tên khách."
                    )

                elif check_out <= check_in:
                    st.error(
                        "Ngày trả phòng phải sau "
                        "ngày nhận phòng."
                    )

                else:

                    success, message = create_booking(
                        full_name,
                        phone,
                        email,
                        id_number,
                        room_id,
                        check_in,
                        check_out,
                        adults,
                        children,
                        note
                    )

                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)


# ============================================================
# KHÁCH LƯU TRÚ
# ============================================================

elif menu == "👤 Khách lưu trú":

    st.title("👤 Quản lý khách lưu trú")

    bookings = fetch_bookings()

    if bookings.empty:

        st.info("Chưa có khách lưu trú.")

    else:

        search_guest = st.text_input(
            "🔎 Tìm kiếm khách",
            placeholder="Nhập tên hoặc số điện thoại"
        )

        filtered = bookings.copy()

        if search_guest:

            mask = (
                filtered["full_name"]
                .astype(str)
                .str.contains(
                    search_guest,
                    case=False,
                    na=False
                )
                |
                filtered["phone"]
                .astype(str)
                .str.contains(
                    search_guest,
                    case=False,
                    na=False
                )
            )

            filtered = filtered[mask]

        st.dataframe(
            filtered[
                [
                    "id",
                    "full_name",
                    "phone",
                    "email",
                    "id_number",
                    "room_number",
                    "room_type",
                    "check_in",
                    "check_out",
                    "adults",
                    "children",
                    "status",
                    "total_amount",
                    "paid_amount",
                    "note"
                ]
            ],
            column_config={
                "id": "Booking ID",
                "full_name": "Khách hàng",
                "phone": "Điện thoại",
                "email": "Email",
                "id_number": "CCCD / Passport",
                "room_number": "Phòng",
                "room_type": "Loại phòng",
                "check_in": "Ngày nhận",
                "check_out": "Ngày trả",
                "adults": "NL",
                "children": "TE",
                "status": "Trạng thái",
                "total_amount": st.column_config.NumberColumn(
                    "Tổng tiền",
                    format="%,.0f VNĐ"
                ),
                "paid_amount": st.column_config.NumberColumn(
                    "Đã thanh toán",
                    format="%,.0f VNĐ"
                ),
                "note": "Ghi chú"
            },
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        st.subheader("🔄 Cập nhật trạng thái")

        booking_options = {
            f"#{row['id']} - {row['full_name']} - "
            f"Phòng {row['room_number']}":
            row["id"]
            for _, row in bookings.iterrows()
        }

        selected_booking = st.selectbox(
            "Chọn booking",
            list(booking_options.keys())
        )

        booking_id = booking_options[selected_booking]

        col1, col2 = st.columns(2)

        with col1:

            new_status = st.selectbox(
                "Trạng thái mới",
                [
                    "Đã đặt",
                    "Đang ở",
                    "Đã trả phòng",
                    "Hủy"
                ]
            )

        with col2:

            if st.button(
                "💾 Cập nhật",
                use_container_width=True
            ):

                success, message = update_booking_status(
                    booking_id,
                    new_status
                )

                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)


# ============================================================
# THANH TOÁN
# ============================================================

elif menu == "💳 Thanh toán":

    st.title("💳 Thanh toán")

    bookings = fetch_bookings()

    if bookings.empty:

        st.info(
            "Chưa có booking để thanh toán."
        )

    else:

        booking_options = {
            f"#{row['id']} - {row['full_name']} - "
            f"Phòng {row['room_number']} - "
            f"{format_money(row['total_amount'])}":
            row["id"]
            for _, row in bookings.iterrows()
        }

        selected = st.selectbox(
            "Chọn booking",
            list(booking_options.keys())
        )

        booking_id = booking_options[selected]

        booking = bookings[
            bookings["id"] == booking_id
        ].iloc[0]

        total_amount = float(
            booking["total_amount"]
        )

        paid_amount = float(
            booking["paid_amount"]
        )

        remaining = max(
            total_amount - paid_amount,
            0
        )

        st.divider()

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Khách hàng",
            booking["full_name"]
        )

        col2.metric(
            "Phòng",
            booking["room_number"]
        )

        col3.metric(
            "Tổng tiền",
            format_money(total_amount)
        )

        col4.metric(
            "Còn lại",
            format_money(remaining)
        )

        st.divider()

        if remaining <= 0:
            st.success(
                "Booking này đã thanh toán đủ."
            )
        else:

            with st.form("payment_form"):

                amount = st.number_input(
                    "Số tiền thanh toán",
                    min_value=0.0,
                    max_value=float(remaining),
                    value=float(remaining),
                    step=100000.0
                )

                method = st.selectbox(
                    "Phương thức thanh toán",
                    [
                        "Tiền mặt",
                        "Chuyển khoản",
                        "Thẻ tín dụng",
                        "Ví điện tử"
                    ]
                )

                note = st.text_area(
                    "Ghi chú thanh toán"
                )

                submit_payment = st.form_submit_button(
                    "💰 Xác nhận thanh toán",
                    use_container_width=True
                )

                if submit_payment:

                    success, message = make_payment(
                        booking_id,
                        amount,
                        method,
                        note
                    )

                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

        st.divider()

        st.subheader("🧾 Lịch sử thanh toán")

        payments = fetch_payments(booking_id)

        if payments.empty:
            st.info(
                "Booking này chưa có giao dịch thanh toán."
            )
        else:
            st.dataframe(
                payments,
                column_config={
                    "id": "ID",
                    "booking_id": "Booking ID",
                    "amount": st.column_config.NumberColumn(
                        "Số tiền",
                        format="%,.0f VNĐ"
                    ),
                    "payment_method": "Phương thức",
                    "payment_date": "Ngày thanh toán",
                    "note": "Ghi chú"
                },
                use_container_width=True,
                hide_index=True
            )


# ============================================================
# AI CHATBOX - TRỢ LÝ KHÁCH SẠN
# ============================================================

def dataframe_to_context(df, max_rows=80):
    """Chuyển DataFrame thành dữ liệu gọn để gửi cho AI."""
    if df is None or df.empty:
        return "Không có dữ liệu."

    data = df.head(max_rows).copy()

    # Chuyển ngày/giờ về chuỗi để JSON không lỗi.
    for col in data.columns:
        try:
            data[col] = data[col].astype(str)
        except Exception:
            pass

    return data.to_json(
        orient="records",
        force_ascii=False,
        date_format="iso"
    )


def build_hotel_ai_context():
    """Lấy snapshot dữ liệu hiện tại từ MySQL cho AI."""
    rooms = get_rooms()
    guests = get_guests()
    bookings = get_bookings()
    payments = get_payments()

    return f"""
DỮ LIỆU HỆ THỐNG QUẢN LÝ KHÁCH SẠN HIỆN TẠI

1. PHÒNG:
{dataframe_to_context(rooms)}

2. KHÁCH:
{dataframe_to_context(guests)}

3. BOOKING:
{dataframe_to_context(bookings)}

4. THANH TOÁN:
{dataframe_to_context(payments)}

Lưu ý: Đây là snapshot dữ liệu hiện tại được lấy trực tiếp từ MySQL Aiven.
Nếu dữ liệu không có thông tin cần hỏi, hãy nói rõ là hệ thống chưa có dữ liệu đó.
Không được tự bịa số phòng, tên khách, booking, số tiền hoặc trạng thái.
"""


def get_openai_api_key():
    """Lấy API key từ Streamlit Secrets hoặc ô nhập sidebar."""
    try:
        secret_key = st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        secret_key = ""

    if secret_key:
        return secret_key

    return st.session_state.get("openai_api_key", "")


def ask_hotel_ai(question):
    """Gửi câu hỏi + dữ liệu MySQL hiện tại cho OpenAI."""
    api_key = get_openai_api_key()

    if not api_key:
        return (
            "Chưa có OpenAI API Key. Bạn hãy nhập API Key ở "
            "phần 🤖 AI Chatbox trong thanh bên trái."
        )

    try:
        client = OpenAI(api_key=api_key)

        context = build_hotel_ai_context()

        # Gửi một số lịch sử gần nhất để cuộc trò chuyện tự nhiên hơn.
        history = st.session_state.get("hotel_chat_messages", [])[-8:]
        history_text = ""

        for item in history:
            history_text += (
                f"{item['role'].upper()}: {item['content']}\n"
            )

        instructions = """
Bạn là AI trợ lý quản lý khách sạn trong ứng dụng Hotel Manager.

Nhiệm vụ:
- Trả lời bằng tiếng Việt, rõ ràng, ngắn gọn và dễ hiểu.
- Có thể trả lời câu hỏi về phòng, trạng thái phòng, giá phòng,
  khách, booking, ngày nhận/trả phòng và thanh toán.
- Dựa vào dữ liệu MySQL được cung cấp trong prompt.
- Khi người dùng hỏi số liệu, phải ưu tiên số liệu trong dữ liệu.
- Không tự bịa dữ liệu.
- Nếu câu hỏi không liên quan đến dữ liệu khách sạn, vẫn có thể trả lời
  ngắn gọn nếu phù hợp, nhưng hãy ưu tiên vai trò trợ lý khách sạn.
- Không tự thực hiện thay đổi dữ liệu trong database.
- Nếu người dùng yêu cầu đặt phòng, xóa phòng, sửa booking hoặc thanh toán,
  hãy hướng dẫn họ dùng chức năng tương ứng trong ứng dụng thay vì giả vờ
  đã thực hiện.
"""

        prompt = f"""
{context}

LỊCH SỬ TRÒ CHUYỆN GẦN ĐÂY:
{history_text}

CÂU HỎI HIỆN TẠI:
{question}
"""

        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=instructions,
            input=prompt,
        )

        answer = response.output_text.strip()

        if not answer:
            return "AI không trả về nội dung. Vui lòng thử lại."

        return answer

    except Exception as e:
        return (
            "Không thể kết nối AI. Kiểm tra OpenAI API Key, Internet "
            f"hoặc cấu hình model. Chi tiết: {e}"
        )


# ============================================================
# GIAO DIỆN CHATBOX
# ============================================================

if "hotel_chat_messages" not in st.session_state:
    st.session_state.hotel_chat_messages = [
        {
            "role": "assistant",
            "content": (
                "Xin chào! 👋 Tôi là AI trợ lý khách sạn. "
                "Bạn có thể hỏi tôi về phòng, khách, booking hoặc thanh toán."
            )
        }
    ]

st.sidebar.divider()
st.sidebar.subheader("🤖 AI Chatbox")

# Cho phép nhập API key trực tiếp nếu chưa cấu hình Secrets.
try:
    has_secret_key = bool(st.secrets.get("OPENAI_API_KEY", ""))
except Exception:
    has_secret_key = False

if not has_secret_key:
    entered_api_key = st.sidebar.text_input(
        "OpenAI API Key",
        type="password",
        value=st.session_state.get("openai_api_key", ""),
        placeholder="sk-...",
        help="API key chỉ dùng trong phiên Streamlit hiện tại."
    )
    st.session_state.openai_api_key = entered_api_key
else:
    st.sidebar.success("OpenAI API Key đã được cấu hình.")

with st.sidebar.expander("💬 Mở chat AI", expanded=False):
    for message in st.session_state.hotel_chat_messages[-8:]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    chat_question = st.chat_input(
        "Hỏi AI về khách sạn...",
        key="hotel_ai_chat_input"
    )

if chat_question:
    st.session_state.hotel_chat_messages.append(
        {
            "role": "user",
            "content": chat_question
        }
    )

    with st.spinner("🤖 AI đang kiểm tra dữ liệu khách sạn..."):
        ai_answer = ask_hotel_ai(chat_question)

    st.session_state.hotel_chat_messages.append(
        {
            "role": "assistant",
            "content": ai_answer
        }
    )

    st.rerun()


# ============================================================
# FOOTER
# ============================================================

st.sidebar.divider()

st.sidebar.caption(
    "🏨 Hotel Manager • Streamlit + MySQL Aiven"
)
