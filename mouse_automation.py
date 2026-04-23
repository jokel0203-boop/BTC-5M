import pyautogui
import time
import json
import keyboard

pyautogui.FAILSAFE = True  # 마우스를 화면 모서리로 이동하면 즉시 중단

WAYPOINTS_FILE = "waypoints.json"


def track_coordinates():
    """현재 마우스 좌표를 실시간으로 출력. Ctrl+C로 종료."""
    print("=== 좌표 추적 모드 ===")
    print("마우스를 원하는 위치에 올리세요. Ctrl+C로 종료.\n")
    try:
        while True:
            x, y = pyautogui.position()
            print(f"X: {x:4d}, Y: {y:4d}", end="\r")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n종료.")


def record_waypoints():
    """F9 키를 누를 때마다 현재 좌표를 기록. Esc로 저장 후 종료."""
    print("=== 좌표 기록 모드 ===")
    print("F9: 현재 위치 저장 | Esc: 완료\n")
    waypoints = []

    while True:
        if keyboard.is_pressed("f9"):
            x, y = pyautogui.position()
            waypoints.append([x, y])
            print(f"저장됨: ({x}, {y})  총 {len(waypoints)}개")
            time.sleep(0.3)

        if keyboard.is_pressed("esc"):
            break

        time.sleep(0.05)

    with open(WAYPOINTS_FILE, "w") as f:
        json.dump(waypoints, f, indent=2)
    print(f"\n{len(waypoints)}개 좌표를 '{WAYPOINTS_FILE}'에 저장했습니다.")
    return waypoints


def load_waypoints():
    """저장된 좌표 파일 불러오기."""
    try:
        with open(WAYPOINTS_FILE, "r") as f:
            waypoints = json.load(f)
        print(f"'{WAYPOINTS_FILE}'에서 {len(waypoints)}개 좌표를 불러왔습니다.")
        return waypoints
    except FileNotFoundError:
        print(f"'{WAYPOINTS_FILE}' 파일이 없습니다. 먼저 좌표를 기록하세요.")
        return []


def run_pattern(waypoints, repeat=1, move_duration=0.5, wait_time=1.0):
    """
    지정된 좌표 순서대로 마우스를 이동.
    repeat: 반복 횟수 (0 = 무한)
    move_duration: 이동 속도(초)
    wait_time: 각 지점 대기 시간(초)
    """
    if not waypoints:
        print("좌표가 없습니다.")
        return

    print(f"\n=== 패턴 실행 ===")
    print(f"좌표 수: {len(waypoints)}  반복: {'무한' if repeat == 0 else repeat}회")
    print("시작까지 3초 대기... (마우스를 화면 모서리로 이동하면 즉시 중단)\n")
    time.sleep(3)

    count = 0
    try:
        while repeat == 0 or count < repeat:
            count += 1
            if repeat != 0:
                print(f"[{count}/{repeat}회]")
            else:
                print(f"[{count}회]")

            for i, (x, y) in enumerate(waypoints):
                pyautogui.moveTo(x, y, duration=move_duration)
                time.sleep(wait_time)

    except pyautogui.FailSafeException:
        print("\n비상 정지 (마우스가 모서리에 닿음)")
    except KeyboardInterrupt:
        print("\nCtrl+C로 중단.")

    print("완료.")


def main():
    print("=== 마우스 자동화 도구 ===\n")
    print("1. 좌표 추적 (실시간 출력)")
    print("2. 좌표 기록 (F9로 저장)")
    print("3. 저장된 좌표로 패턴 실행")
    print("4. 직접 좌표 입력 후 실행")
    print()

    choice = input("선택 (1~4): ").strip()

    if choice == "1":
        track_coordinates()

    elif choice == "2":
        record_waypoints()

    elif choice == "3":
        waypoints = load_waypoints()
        if waypoints:
            repeat = int(input("반복 횟수 (0=무한): "))
            move_duration = float(input("이동 속도 (초, 예: 0.5): "))
            wait_time = float(input("지점 대기 시간 (초, 예: 1.0): "))
            run_pattern(waypoints, repeat, move_duration, wait_time)

    elif choice == "4":
        print("좌표를 입력하세요. 빈 줄 입력 시 완료.")
        waypoints = []
        while True:
            line = input(f"  좌표 {len(waypoints)+1} (x,y 형식, 예: 500,300): ").strip()
            if not line:
                break
            try:
                x, y = map(int, line.split(","))
                waypoints.append([x, y])
            except ValueError:
                print("  형식 오류. 다시 입력하세요.")

        if waypoints:
            repeat = int(input("반복 횟수 (0=무한): "))
            move_duration = float(input("이동 속도 (초, 예: 0.5): "))
            wait_time = float(input("지점 대기 시간 (초, 예: 1.0): "))
            run_pattern(waypoints, repeat, move_duration, wait_time)

    else:
        print("잘못된 선택입니다.")


if __name__ == "__main__":
    main()
