import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from math import pi
import requests
import json
import base64
from io import BytesIO
from PIL import Image
import matplotlib.font_manager as fm

# 한글 폰트 설정 (한글 깨짐 방지)
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['axes.unicode_minus'] = False

# 페이지 기본 설정 (페이지 제목: 시멘트 소성로 멀티사이클론 설계 시뮬레이터)
st.set_page_config(page_title="Cement Kiln Multi-Cyclone Design Simulator", page_icon="🏭", layout="wide")
st.title("🏭 Cement Kiln Multi-Cyclone Design Simulator")
st.markdown("""
This simulator predicts dust removal efficiency and pressure loss for **parallel modular multi-cyclone** dust collectors
in cement kiln applications, based on key design parameters.
""")

# 사이클론 집진 장치 선정 가이드 섹션 추가
st.markdown("""
### 📚 사이클론 집진 장치 선정 가이드

#### 1. 사이클론의 기본 원리
- **원심력 활용**: 회전하는 기류에서 분진 입자를 벽면으로 분리
- **중력 활용**: 분리된 분진을 하부로 낙하시켜 수집
- **효율적 집진**: 5μm 이상의 입자에 대해 80-90% 이상의 집진 효율

#### 2. 시멘트 소성로 적용 시 고려사항
- **입자 크기**: 1-100μm 범위의 시멘트 분진 처리
- **가스 온도**: 200-400℃ 범위의 고온 가스 처리
- **분진 농도**: 5-50g/m³ 범위의 고농도 분진 처리
- **부식성**: 알칼리성 분진에 대한 내구성 고려

#### 3. 사이클론 선정 기준
- **처리 유량**: 시멘트 소성로 배출가스량에 따른 적정 크기 선정
- **압력 손실**: 1000-2000Pa 범위의 허용 압력 손실 고려
- **설치 공간**: 소성로 주변 공간 제약 고려
- **유지보수**: 분진 배출 및 청소 용이성 검토

#### 4. 멀티사이클론 구성 시 장점
- **높은 처리량**: 단일 사이클론 대비 2-3배 처리량 증가
- **효율 향상**: 병렬 구성으로 집진 효율 5-10% 향상
- **공간 효율**: 정사각형/육각형 배치로 설치 공간 최적화
- **운전 안정성**: 일부 사이클론 고장 시에도 연속 운전 가능

#### 5. 시멘트 소성로 적용 시 주의사항
- **내마모성**: 시멘트 분진의 마모성 고려한 재질 선정
- **온도 영향**: 고온 가스로 인한 열팽창 고려
- **분진 응집**: 고온에서의 분진 응집성 고려
- **배출가스 성분**: SOx, NOx 등 부식성 가스 성분 고려
""")

# ------------ 입력 파라미터 섹션 ------------
col1, col2 = st.columns([1, 2])

with col1:
    st.header("📥 설계 파라미터")  # 설계 입력 파라미터
    
    # 기본 탭 구성 (주요 치수, 유체/입자, 멀티사이클론 설정)
    tabs = st.tabs(["치수", "유체/입자", "멀티사이클론 설정"])
    
    # 주요 치수 탭
    with tabs[0]:
        # 단일 사이클론 직경 (D)
        D = st.number_input("단일 사이클론 직경 D (m)", value=0.04, min_value=0.01, max_value=0.5, step=0.001,
                          help="시멘트 소성로 적용 시 권장 ≤ 0.15m")
        # 입구 너비 (a)
        a = st.number_input("입구 너비 a (m)", value=0.02, min_value=0.005, max_value=0.2, step=0.001,
                          help="시멘트 먼지 특성 고려")
        # 입구 높이 (b)
        b = st.number_input("입구 높이 b (m)", value=0.04, min_value=0.01, max_value=0.3, step=0.001,
                          help="시멘트 먼지 특성 고려")
        # 원통부 높이 (H)
        H = st.number_input("원통부 높이 H (m)", value=0.16, min_value=0.05, max_value=1.0, step=0.005,
                          help="시멘트 먼지 분리 효율 고려")
        # 원추부 높이 (h)
        h = st.number_input("원추부 높이 h (m)", value=0.16, min_value=0.05, max_value=1.0, step=0.005,
                          help="시멘트 먼지 수집 효율 고려")
        # 배출구 직경 (B)
        B = st.number_input("먼지 배출구 직경 B (m)", value=0.02, min_value=0.005, max_value=0.1, step=0.001,
                          help="시멘트 먼지 배출 특성 고려")
        # 찾아관 침입 깊이 (S)
        S = st.number_input("찾아관 침입 깊이 S (m)", value=0.05, min_value=0.0, max_value=0.3, step=0.001,
                          help="시멘트 먼지 재비산 방지")
        # 찾아관 직경 (De)
        De = st.number_input("찾아관 직경 De (m)", value=0.02, min_value=0.01, max_value=0.2, step=0.001,
                          help="시멘트 먼지 재비산 방지")
    
    # 유체/입자 탭
    with tabs[1]:
        # 유입 속도 (V)
        V_in = st.number_input("유입 속도 V (m/s)", value=15.083, min_value=5.0, max_value=50.0,
                             help="시멘트 먼지 제거를 위한 권장 ≥ 20m/s")
        # 총 처리 유량 (Q)
        Q_total = st.number_input("총 처리 유량 Q (m³/s)", value=625/60, min_value=0.1, max_value=20.0, step=0.1,
                                help="시멘트 소성로 배출가스 처리량")
        
        # 공기 점도 (μ)
        mu = st.number_input("공기 점도 μ (kg/m·s)", value=0.10728/3600, format="%.2e",
                           help="시멘트 소성로 배출가스 온도 고려")
        # 공기 밀도 (ρₐ)
        rho_g = st.number_input("공기 밀도 ρₐ (kg/m³)", value=0.5975, min_value=0.1, max_value=10.0, step=0.1,
                              help="시멘트 소성로 배출가스 온도 고려")
        # 입자 밀도 (ρₚ)
        rho_p = st.number_input("입자 밀도 ρₚ (kg/m³)", value=480.0, min_value=100.0, max_value=10000.0,
                              help="시멘트 먼지 밀도")
        
        # 분석할 입자 크기 범위
        dp_range = st.slider("입자 크기 범위 (μm)", 
                        min_value=0.1, max_value=10.0, value=(0.1, 10.0),
                        help="시멘트 먼지 특성 분석")
        # 목표 입자 직경
        dp_target = st.slider("목표 입자 직경 dₚ (μm)", 
                          min_value=dp_range[0], max_value=dp_range[1], value=2.5,
                          help="시멘트 먼지 주요 크기")
        dp_target_m = dp_target * 1e-6  # 마이크론을 미터로 변환
    
    # 멀티사이클론 설정 탭
    with tabs[2]:
        # 사이클론 수 선택 (1개 또는 2개)
        n_cyclones = st.selectbox("사이클론 수", [1, 2], index=0,
                                help="시멘트 소성로 처리량에 따른 구성")
        # 배치 방식 (2개일 때만 선택 가능)
        layout_type = st.selectbox("배치 방식", ["정사각형", "육각형"], index=0,
                                 help="시멘트 소성로 공간 제약 고려",
                                 disabled=(n_cyclones == 1))
        # 효율 계산 모델 선택
        model_type = st.selectbox("효율 계산 모델", 
                              ["시멘트 먼지 최적화", "Lapple", "Stairmand"], index=1,
                              help="시멘트 먼지 특성에 맞는 모델 선택")
        # 유효 회전수 (더 이상 직접 입력받지 않고 계산)
        # N_turns = st.number_input("유효 회전수 Ne", value=8.0, min_value=5.0, max_value=12.0, step=0.5, 
        #                        help="시멘트 먼지 제거를 위한 권장 ≥ 8")

# ------------ 계산 모델 섹션 ------------
# 주요 파라미터 계산
A_in = a * b  # 단일 사이클론 입구 단면적
Q_single = V_in * A_in  # 단일 사이클론 유량
n_cyclones = max(1, int(np.ceil(Q_total / Q_single)))  # 필요한 사이클론 수 자동 계산 (최소 1개)

# 유효 회전수 Ne 계산 (이미지 공식 적용: Ne = 1/b * [H + h/2])
# H는 원통부 높이, h는 원추부 높이, b는 입구 높이
if b > 0:
    N_turns = (1 / b) * (H + h / 2)
else:
    N_turns = 8.0 # b가 0일 경우 기본값 설정 또는 오류 처리

# 유속 계산
V_t = V_in  # 접선 속도 (입구 속도와 동일하다고 가정)
# V_r = Q_single / (pi * D * H)  # 반경 방향 속도 (현재 사용되지 않음)

# Cut-size 계산 함수 (dp₅₀: 50% 제거 효율을 보이는 입자 크기)
def calculate_stk50(a, mu, V_in, N_turns, rho_p, rho_g, model_type):
    """Cut-size parameter dp₅₀ 계산 함수 (이미지 공식 반영)"""
    # 이미지 공식: dpc = sqrt(9 * mu * W / (2 * pi * Ne * Vi * (rho_p - rho_g)))
    # W는 입구 너비 a, Vi는 유입 속도 V_in
    
    if (rho_p - rho_g) <= 0 or N_turns <= 0 or V_in <= 0:
         return float('inf') # 물리적으로 불가능한 경우 inf 반환
         
    numerator = 9 * mu * a
    denominator = 2 * pi * N_turns * V_in * (rho_p - rho_g)
    
    # 선택된 모델에 따라 추가 계수 적용 또는 동일 공식 사용
    if model_type == "시멘트 먼지 최적화":
        # 이미지 공식 기반 + 시멘트 먼지 최적화 계수 (예: 0.8)
        return np.sqrt(numerator / denominator) * 0.8
    elif model_type == "Lapple":  # Lapple 모델 (이미지 공식과 유사)
        return np.sqrt(numerator / denominator)
    else:  # Stairmand 모델 (기존 Stairmand 공식 유지 또는 조정 필요)
        # Stairmand는 보통 다른 형태의 공식을 사용하므로 여기서는 이미지 공식을 적용하지 않습니다.
        # 필요하다면 Stairmand 공식으로 대체하거나 별도의 계산 로직을 구현해야 합니다.
        # 여기서는 단순화를 위해 Lapple과 동일한 공식 사용 (조정 필요)
         st.warning("Stairmand 모델은 이미지의 공식과 다를 수 있습니다. 결과 해석에 유의하세요.")
         return np.sqrt(numerator / denominator)

# 압력 손실 계산 함수
def calculate_pressure_loss(model_type, rho_g, V_in):
    """사이클론 압력 손실 계산"""
    # 항력 계수 선택
    if model_type == "시멘트 먼지 최적화":  # 시멘트 먼지 최적화 모델
        K = 10  # 예시 계수, 실제 데이터 기반 조정 필요
    elif model_type == "Lapple":  # Lapple 모델
        K = 16 # 이미지 Input 조건의 K값 반영
    else:  # Stairmand 모델
        K = 8 # 예시 계수
    
    # 압력 손실 계산 (Pa) delta_P = 0.5 * rho_g * V_in^2 * K
    delta_P = 0.5 * rho_g * V_in**2 * K
    
    return delta_P

# Cut-size 계산 (dp50) - 이미지 공식 사용
dp50 = calculate_stk50(a, mu, V_in, N_turns, rho_p, rho_g, model_type) * 1e6  # m to μm

# 입자 크기별 효율 계산 함수
def calculate_efficiency(dp_microns):
    """입자 크기별 집진 효율 계산"""
    # np.where를 사용하여 dp_microns가 0보다 클 때만 효율을 계산하고, 그렇지 않으면 0을 반환합니다.
    
    # 모델별 효율 계산
    if model_type == "시멘트 먼지 최적화":  # 시멘트 먼지 최적화 모델
        # 이미지 공식 기반 효율 곡선 (예: 1 - exp(-k * (dp/dp50)^2))
        # dp50이 무한대가 아닌 경우에만 계산
        if np.isinf(dp50) or dp50 <= 0:
             return np.zeros_like(dp_microns) # dp50이 유효하지 않으면 효율 0
        return np.where(dp_microns > 0, 1 - np.exp(-2.5 * (dp_microns / dp50)**2), 0)
        
    elif model_type == "Lapple":  # Lapple 모델
        # Lapple 효율 공식: eta = 1 / (1 + (dp50 / dp)^2)
        # dp_microns가 0보다 크고 dp50이 무한대가 아닌 경우에만 계산
        if np.isinf(dp50) or dp50 <= 0:
             return np.zeros_like(dp_microns) # dp50이 유효하지 않으면 효율 0
        return np.where(dp_microns > 0, 1 / (1 + (dp50 / dp_microns)**2), 0)
        
    else:  # Stairmand 모델
        # Stairmand 효율 공식 (예시) - 이미지 공식과 형태 유사
        # dp_microns가 0보다 크고 dp50이 무한대가 아닌 경우에만 계산
        if np.isinf(dp50) or dp50 <= 0:
             return np.zeros_like(dp_microns) # dp50이 유효하지 않으면 효율 0
        st.warning("Stairmand 모델은 이미지의 공식과 다를 수 있습니다. 결과 해석에 유의하세요.")
        return np.where(dp_microns > 0, 1 - np.exp(-2 * (dp_microns / dp50)**2), 0)

# 입자 크기별 효율 곡선 데이터 준비
dp_array = np.linspace(dp_range[0], dp_range[1], 100)
eta_array = calculate_efficiency(dp_array)
eta_multi_array = 1 - (1 - eta_array)**n_cyclones

# 입자 크기 분포 데이터 (첨부 이미지 기반)
particle_distribution_data = [
    {"size_range": "1~5", "dp_avg": 2.5, "Mj_percent": 5},
    {"size_range": "5~10", "dp_avg": 7.5, "Mj_percent": 10},
    {"size_range": "10~20", "dp_avg": 15, "Mj_percent": 15},
    {"size_range": "20~40", "dp_avg": 30, "Mj_percent": 20},
    {"size_range": "40~60", "dp_avg": 50, "Mj_percent": 20},
    {"size_range": "60~80", "dp_avg": 70, "Mj_percent": 15},
    {"size_range": "80~100", "dp_avg": 90, "Mj_percent": 10},
    {"size_range": "100+", "dp_avg": 100, "Mj_percent": 5},
]

# ------------ 결과 출력 섹션 ------------
with col2:
    st.header("📊 계산 결과 및 시각화")  # 계산 결과 및 시각화
    
    # 계산 결과 표시
    result_col1, result_col2 = st.columns(2)
    
    with result_col1:
        st.subheader("성능 지표")  # 성능 지표
        st.markdown(f"- Cut-size Diameter (dp₅₀): **{dp50:.2f} μm**")  # Cut-size 직경
        st.markdown(f"- 단일 사이클론 효율 ({dp_target} μm): **{calculate_efficiency(dp_target):.2%}**")  # 단일 사이클론 효율 (단일 값으로 재계산)
        st.markdown(f"- 멀티사이클론 누적 효율 ({dp_target} μm): **{(1 - (1 - calculate_efficiency(dp_target))**n_cyclones):.2%}**")  # 멀티사이클론 누적 효율 (단일 값으로 재계산)
        st.markdown(f"- 예상 압력 손실: **{calculate_pressure_loss(model_type, rho_g, V_in):.1f} Pa**")  # 예상 압력 손실
        st.markdown(f"- 총 처리 유량: **{Q_total:.2f} m³/s**")  # 총 처리 유량
        st.markdown(f"- 필요 사이클론 수: **{n_cyclones}**")  # 필요 사이클론 수
    
    with result_col2:
        st.subheader("주요 설계 비율")  # 주요 설계 비율
        # 사이클론 치수 비율 계산
        a_D_ratio = a/D  # 입구 너비/직경 비율
        b_D_ratio = b/D  # 입구 높이/직경 비율
        S_D_ratio = S/D  # 찾아관 침입 깊이/직경 비율
        De_D_ratio = De/D  # 찾아관 직경/직경 비율
        H_D_ratio = H/D  # 원통부 높이/직경 비율
        h_D_ratio = h/D  # 원추부 높이/직경 비율
        B_D_ratio = B/D  # 배출구 직경/직경 비율
        
        # 비율 표시
        ratios_df = pd.DataFrame({
            'Design Ratio': ['a/D', 'b/D', 'S/D', 'De/D', 'H/D', 'h/D', 'B/D'],
            'Current Value': [a_D_ratio, b_D_ratio, S_D_ratio, De_D_ratio, H_D_ratio, h_D_ratio, B_D_ratio],
            'Recommended Range': ['0.3-0.5', '0.3-0.7', '0.3-0.8', '0.4-0.6', '2.0-4.0', '1.5-3.0', '0.2-0.4']
        })
        st.dataframe(ratios_df, hide_index=True)
    
st.subheader("📊 입자 크기별 및 전체 집진 효율")  # 입자 크기별 및 전체 집진 효율

efficiency_results = []
overall_single_efficiency = 0.0  # 누적 효율 (0~1 범위 소수)

for item in particle_distribution_data:
    size_range = item["size_range"]
    dp_avg = item["dp_avg"]
    Mj_percent = item["Mj_percent"]

    # 단일 사이클론 효율 계산
    eta_single_dp = calculate_efficiency(dp_avg)

    # Cut-size 대비 입자 크기 비율
    dpc_dp = dp50 / dp_avg if dp_avg > 0 else float('inf')

    # Nj 계산: Nj = 1/(1+(dpc/dp)^2)
    Nj = 1 / (1 + dpc_dp**2) if not np.isinf(dpc_dp) else 0

    # % collected 계산 (소수 값)
    collected_single_percent = Nj * (Mj_percent / 100)
    overall_single_efficiency += collected_single_percent  # 누적 효율은 소수 상태로 유지

    # 표에 출력용 데이터 저장 (소수→퍼센트 변환 포함)
    efficiency_results.append({
        "size range": size_range,
        "dp avg": dp_avg,
        "dpc/dp": f"{dpc_dp:.4f}",
        "Nj": f"{Nj:.6f}",
        "Mj%": Mj_percent,
        "% collected": f"{collected_single_percent * 100:.6f}"
    })

# 데이터프레임 정리 및 출력
efficiency_df = pd.DataFrame(efficiency_results)
efficiency_df = efficiency_df[["size range", "dp avg", "dpc/dp", "Nj", "Mj%", "% collected"]]
st.dataframe(efficiency_df, hide_index=True)

# 단일 사이클론 전체 효율 출력 (소수 → 퍼센트)
st.markdown(f"**Overall Effic =** **{overall_single_efficiency * 100:.2f}%**")

# 멀티사이클론 전체 효율 계산
overall_multi_efficiency_image = (1 - (1 - overall_single_efficiency) ** 2) * 100
st.markdown(f"**멀티 효율 =** **{overall_multi_efficiency_image:.6f}%**")

# ⚠️ 100% 초과 시 경고
if overall_single_efficiency > 1.0:
    st.warning("⚠️ 단일 사이클론 누적 효율이 100%를 초과했습니다. 입력된 입자 분포나 파라미터를 다시 확인하세요.")
    
    
    # 시각화 부분
    graph_col1, graph_col2 = st.columns(2)
    
    with graph_col1:
        st.subheader("Particle Size Efficiency Curve")  # 입자 크기별 효율 곡선
        fig1, ax1 = plt.subplots(figsize=(6, 4))

        # 효율 곡선 그리기
        ax1.plot(dp_array, eta_array, label="Single Cyclone")  # 단일 사이클론
        ax1.plot(dp_array, eta_multi_array, linestyle='--', label=f"{n_cyclones} Parallel")  # 병렬 배치
        ax1.axvline(x=dp_target, color='red', linestyle=':', alpha=0.7)  # 목표 입자 크기
        
        # 목표 입자 크기(dp_target)에서의 단일 및 멀티사이클론 효율 점을 올바르게 계산하여 표시
        eta_target_single = calculate_efficiency(dp_target) # 단일 사이클론 효율 계산
        eta_target_multi = 1 - (1 - eta_target_single)**n_cyclones # 멀티사이클론 효율 계산
        
        ax1.plot(dp_target, eta_target_single, 'ro', ms=6)  # 단일 사이클론 효율 점
        ax1.plot(dp_target, eta_target_multi, 'ro', ms=6)  # 멀티사이클론 효율 점

        # 기준선 및 주석
        ax1.axhline(y=0.5, color='gray', linestyle='--', alpha=0.4)  # 50% 효율 기준선
        ax1.axvline(x=dp50, color='gray', linestyle='--', alpha=0.5)  # Cut-size 기준선
        ax1.text(dp50 + 0.1, 0.52, "cut-size (dp₅₀)", fontsize=9, color='gray')

        # 라벨링
        ax1.set_xlabel("Particle Diameter (μm)", fontsize=11)  # 입자 직경
        ax1.set_ylabel("Collection Efficiency", fontsize=11)  # 집진 효율
        ax1.set_title(f"PM2.5 Collection Efficiency - {model_type}", fontsize=13)  # PM2.5 집진 효율
        ax1.grid(True, alpha=0.3)
        ax1.legend(fontsize=9)

        # 강조 텍스트
        ax1.text(dp_target + 0.1, eta_target_multi, 
                f"dp = {dp_target} μm", fontsize=9, color='red')

        st.pyplot(fig1)
    
    with graph_col2:
        st.subheader("Cyclone Layout Diagram")  # 사이클론 배치 다이어그램
        
        # 사이클론 배치 시각화
        fig2, ax2 = plt.subplots(figsize=(8, 8))
        
        # 전체 시스템 경계 그리기
        if n_cyclones == 1:
            # 단일 사이클론 시스템
            total_width = D * 2
            total_height = D * 3
            rect = plt.Rectangle((-total_width/2, -total_height/2), total_width, total_height, 
                               fill=False, color='gray', linestyle='--', alpha=0.5)
            ax2.add_patch(rect)
            
            # 공통 입구 덕트 그리기
            inlet_width = total_width * 0.8
            inlet_height = D * 0.3
            inlet = plt.Rectangle((-inlet_width/2, total_height/2), inlet_width, inlet_height,
                                fill=True, color='lightgray', alpha=0.3)
            ax2.add_patch(inlet)
            ax2.arrow(0, total_height/2 + inlet_height, 0, -inlet_height/2, 
                     head_width=inlet_width/4, head_length=inlet_height/2, fc='blue', ec='blue')
            
            # 사이클론 본체 그리기
            # 원통부
            cylinder = plt.Rectangle((-D/2, -D/2), D, D, fill=False, color='blue')
            ax2.add_patch(cylinder)
            # 원추부
            cone = plt.Polygon([(-D/2, -D/2), (D/2, -D/2), (0, -D*1.5)], 
                             fill=False, color='blue')
            ax2.add_patch(cone)
            
            # 입구 화살표
            ax2.arrow(D/2, 0, D/4, 0, head_width=0.05*D, head_length=0.05*D, fc='green', ec='green')
            # 출구 화살표
            ax2.arrow(0, -D*1.5, 0, -D/4, head_width=0.05*D, head_length=0.05*D, fc='red', ec='red')
            
        else:  # 2개의 사이클론
            spacing = D * 1.5  # 사이클론 간 간격
            
            # 전체 시스템 경계 그리기
            total_width = spacing + D * 2
            total_height = D * 3
            rect = plt.Rectangle((-total_width/2, -total_height/2), total_width, total_height, 
                               fill=False, color='gray', linestyle='--', alpha=0.5)
            ax2.add_patch(rect)
            
            # 공통 입구 덕트 그리기
            inlet_width = total_width * 0.8
            inlet_height = D * 0.3
            inlet = plt.Rectangle((-inlet_width/2, total_height/2), inlet_width, inlet_height,
                                fill=True, color='lightgray', alpha=0.3)
            ax2.add_patch(inlet)
            ax2.arrow(0, total_height/2 + inlet_height, 0, -inlet_height/2, 
                     head_width=inlet_width/4, head_length=inlet_height/2, fc='blue', ec='blue')
            
            # 두 개의 사이클론 그리기
            for i in range(2):
                x = (i - 0.5) * spacing
                
                # 사이클론 본체 그리기
                # 원통부
                cylinder = plt.Rectangle((x-D/2, -D/2), D, D, fill=False, color='blue')
                ax2.add_patch(cylinder)
                # 원추부
                cone = plt.Polygon([(x-D/2, -D/2), (x+D/2, -D/2), (x, -D*1.5)], 
                                 fill=False, color='blue')
                ax2.add_patch(cone)
                
                # 입구 화살표
                ax2.arrow(x+D/2, 0, D/4, 0, head_width=0.05*D, head_length=0.05*D, fc='green', ec='green')
                # 출구 화살표
                ax2.arrow(x, -D*1.5, 0, -D/4, head_width=0.05*D, head_length=0.05*D, fc='red', ec='red')
                
                # 사이클론 번호
                ax2.text(x, 0, f"{i+1}", ha='center', va='center', color='blue', fontweight='bold')
        
        # 범례 추가
        legend_elements = [
            plt.Line2D([0], [0], color='blue', label='Cyclone Body', linestyle='-'),
            plt.Line2D([0], [0], color='green', label='Inlet Flow', marker='>', linestyle='None'),
            plt.Line2D([0], [0], color='red', label='Outlet Flow', marker='v', linestyle='None'),
            plt.Rectangle((0, 0), 1, 1, fill=True, color='lightgray', alpha=0.3, label='Inlet Duct')
        ]
        ax2.legend(handles=legend_elements, loc='upper center', bbox_to_anchor=(0.5, -0.05),
                  ncol=2, frameon=True)
        
        # 축 설정
        ax2.set_aspect('equal')
        ax2.set_xlim(-D*4, D*4)
        ax2.set_ylim(-D*4, D*4)
        ax2.set_title(f"{'Single' if n_cyclones == 1 else 'Dual'} Cyclone Configuration\nFlow Direction and System Structure", 
                     fontsize=12, pad=20)
        ax2.axis('off')
        
        st.pyplot(fig2)

# --- 참고 안내 ---
st.info("""
💡 **시멘트 소성로 멀티사이클론 설계 가이드**:
- **시멘트 먼지 최적화 모델**: 시멘트 먼지 특성에 맞춘 집진 효율 계산
- **높이 제한**: 시멘트 소성로 설치 공간 고려하여 단일 사이클론 직경 ≤ 0.15m 권장
- **구성**: 시멘트 소성로 처리량에 따라 단일 또는 이중 사이클론 선택
- **유입 속도**: 시멘트 먼지 제거를 위해 20m/s 이상 권장
- **온도 영향**: 시멘트 소성로 배출가스 온도에 따른 공기 물성 변화 고려

이 시뮬레이터는 이론적 모델을 기반으로 하며, 실제 실험 또는 CFD 결과와 차이가 있을 수 있습니다.
정밀한 설계를 위해서는 실험 데이터로 검증이 필요합니다.
""")

# --- 다운로드 기능 ---
@st.cache_data
def convert_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

# 계산 결과 데이터프레임 생성
results_df = pd.DataFrame({
    'Particle Diameter (μm)': dp_array,  # 입자 직경
    'Single Efficiency': eta_array,  # 단일 사이클론 효율
    'Multi Efficiency': eta_multi_array  # 멀티사이클론 효율
})

st.download_button(
    label="Download Results CSV",  # 계산 결과 CSV 다운로드
    data=convert_to_csv(results_df),
    file_name='multicyclone_efficiency_results.csv',
    mime='text/csv',
)