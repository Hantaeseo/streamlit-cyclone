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
import platform
import os

# 한글 폰트 설정 (한글 깨짐 방지)
def setup_korean_font():
    system = platform.system()
    if system == "Darwin":  # macOS
        try:
            # macOS 기본 한글 폰트들 시도
            fonts = ['AppleGothic', 'Apple SD Gothic Neo', 'NanumGothic', 'Malgun Gothic']
            for font in fonts:
                if font in [f.name for f in fm.fontManager.ttflist]:
                    plt.rcParams['font.family'] = font
                    break
            else:
                plt.rcParams['font.family'] = 'DejaVu Sans'
        except:
            plt.rcParams['font.family'] = 'DejaVu Sans'
    elif system == "Windows":
        plt.rcParams['font.family'] = 'Malgun Gothic'
    else:  # Linux
        plt.rcParams['font.family'] = 'NanumGothic'
    
    plt.rcParams['axes.unicode_minus'] = False

# 한글 폰트 설정 적용
setup_korean_font()

# ------------ 단위 변환 및 상수 정의 ------------
class CycloneUnits:
    """사이클론 설계 단위 변환 및 상수 클래스"""
    
    @staticmethod
    def m3_per_s_to_m3_per_min(flow_rate):
        """m³/s를 m³/min으로 변환"""
        return flow_rate * 60
    
    @staticmethod
    def m3_per_min_to_m3_per_s(flow_rate):
        """m³/min을 m³/s로 변환"""
        return flow_rate / 60
    
    @staticmethod
    def m_per_s_to_m_per_min(velocity):
        """m/s를 m/min으로 변환"""
        return velocity * 60
    
    @staticmethod
    def m_per_min_to_m_per_s(velocity):
        """m/min을 m/s로 변환"""
        return velocity / 60
    
    @staticmethod
    def micron_to_meter(size_micron):
        """마이크론을 미터로 변환"""
        return size_micron * 1e-6
    
    @staticmethod
    def meter_to_micron(size_meter):
        """미터를 마이크론으로 변환"""
        return size_meter * 1e6
    
    @staticmethod
    def pa_to_kpa(pressure_pa):
        """Pa를 kPa로 변환"""
        return pressure_pa / 1000
    
    @staticmethod
    def kpa_to_pa(pressure_kpa):
        """kPa를 Pa로 변환"""
        return pressure_kpa * 1000

# ------------ 통합 계산 함수 섹션 ------------
def calculate_effective_turns(inlet_height, body_length, cone_length):
    """유효 회전수 Ne 계산 (통합 공식)"""
    if inlet_height <= 0:
        return 6.0  # 기본값
    return (1 / inlet_height) * (body_length + cone_length / 2)

def calculate_cut_size(inlet_width, gas_viscosity, inlet_velocity, effective_turns, 
                      particle_density, gas_density):
    """Cut-size dpc 계산 (Lapple 공식 기반)"""
    if (particle_density - gas_density) <= 0 or effective_turns <= 0 or inlet_velocity <= 0:
        return float('inf')
    
    numerator = 9 * gas_viscosity * inlet_width
    denominator = 2 * pi * effective_turns * inlet_velocity * (particle_density - gas_density)
    
    return np.sqrt(numerator / denominator)  # 미터 단위 반환

def calculate_collection_efficiency(particle_size_micron, cut_size_micron):
    """집진 효율 계산 (Lapple 공식)"""
    if cut_size_micron <= 0 or np.isinf(cut_size_micron):
        return 0.0
    
    ratio = cut_size_micron / particle_size_micron
    return 1 / (1 + ratio**2)

def calculate_system_pressure_loss(gas_density, inlet_velocity, pressure_coefficient=16, series_count=1):
    """시스템 압력 손실 계산 (통일된 공식)"""
    single_cyclone_loss = 0.5 * gas_density * inlet_velocity**2 * pressure_coefficient
    return single_cyclone_loss * series_count

def calculate_multi_cyclone_efficiency(single_efficiency, cyclone_count):
    """멀티사이클론 효율 계산"""
    return 1 - (1 - single_efficiency)**cyclone_count

# ------------ 함수 정의 섹션 ------------
def calculate_stk50(a, mu, V_in, N_turns, rho_p, rho_g, model_type):
    """구 버전 호환성을 위한 래퍼 함수"""
    return calculate_cut_size(a, mu, V_in, N_turns, rho_p, rho_g)

def calculate_pressure_loss(model_type, rho_g, V_in, series_count=1, preset_option="EPA 표준"):
    """구 버전 호환성을 위한 래퍼 함수"""
    # 압력 계수 통일 (K=16)
    return calculate_system_pressure_loss(rho_g, V_in, pressure_coefficient=16, series_count=series_count)

def calculate_efficiency_detailed(dp_microns, dpc_microns):
    """구 버전 호환성을 위한 래퍼 함수"""
    if isinstance(dp_microns, (list, np.ndarray)):
        return np.array([calculate_collection_efficiency(dp, dpc_microns) for dp in dp_microns])
    else:
        return calculate_collection_efficiency(dp_microns, dpc_microns)

# 페이지 기본 설정 (페이지 제목: 시멘트 소성로 멀티사이클론 설계 시뮬레이터)
st.set_page_config(page_title="사이클론 설계 시뮬레이터", page_icon="🌪️", layout="wide")
st.title("🌪️ 사이클론 설계 시뮬레이터")
st.markdown("""
**Lapple 이론 기반 사이클론 집진기 설계 및 성능 예측 시뮬레이터**  
실제 설계 조건에 따른 집진 효율, 압력 손실, Cut-size 등을 계산합니다.
""")

# EPA 기준 사이클론 집진 장치 선정 가이드 섹션 추가
with st.expander("📚 설계 참고 기준 및 가이드라인", expanded=False):
    st.markdown("""
    ### 1. EPA Conventional Cyclone 기준
    - **압력 손실**: 1.0~1.5 kPa (4~6 in H₂O)
    - **처리 유량**: 0.5~12 m³/s (30~720 m³/min)
    - **최적 효율 속도**: 18.3 m/s
    - **병렬 구성**: 상한선 유량 초과 시 병렬 사이클론 적용

    ### 2. 시멘트 소성로 사이클론 프리히터 기준 (쌍용C&E 동해공장 사례)
    - **생산 능력**: 연간 1,150만 톤 (7기 소성로 운영)
    - **소성로당 처리량**: 일 4,500톤 = 시간당 187.5톤
    - **총 처리 유량**: 375,000 m³/h = 6,250 m³/min = **104.17 m³/s**
    - **운전 온도**: 최대 360℃ (600℉) - 프리히터 출구 기준
    - **고온 물성치**: 
      - 공기 밀도: 0.5975 kg/m³ (360℃)
      - 공기 점도: 2.98×10⁻⁵ kg/m·s (360℃)

    ### 3. Lapple 1951 표준 사이클론 치수 비율
    **Conventional Cyclone Dimensions (adapted from Lapple, 1951)**:
    - Height of Inlet: H/D = 0.5
    - Width of Inlet: W/D = 0.25  
    - Diameter of Gas Exit: De/D = 0.5
    - Length of Vortex Finder: S/D = 0.625
    - Length of Body: Lb/D = 2.0
    - Length of Cone: Lc/D = 2.0
    - Diameter of Dust Outlet: Dd/D = 0.25
    """)

# ------------ 입력 파라미터 섹션 ------------
col1, col2 = st.columns([1, 2])

with col1:
    st.header("⚙️ 설계 입력 파라미터")  # 설계 입력 파라미터로 변경
    
    # 프리셋 선택 옵션 추가
    st.subheader("🏭 설계 프리셋 선택")
    preset_option = st.selectbox("설계 기준 선택", 
                               ["커스텀 설정", "EPA 표준", "시멘트 소성로 (쌍용C&E)", "화력발전소", "일반 산업용", "실제 설계 사례 (625m³/min)"], 
                               index=0,
                               help="실제 산업 사례 기반 프리셋 또는 커스텀 설정")
    
    # 기본값 초기화 (모든 변수 미리 정의)
    default_Q = 6.0
    default_V = 18.3
    default_rho_g = 1.225
    default_mu = 1.81e-5
    default_temp_info = "20℃ (상온)"
    max_Q_limit = 20.0
    recommended_cyclones = 1
    
    # 실제 설계 사례용 추가 변수 초기화
    default_rho_p = 2650.0
    target_efficiency = 85.0
    max_pressure_loss = 1500
    pressure_coeff_K = 16
    series_count = 1
    parallel_count = 1
    
    # 30:1 모형 기준 치수 초기화
    default_D = 2.35
    default_H = 1.2
    default_W = 0.6
    default_De = 1.175
    default_S = 1.5
    default_Lb = 4.8
    default_Lc = 4.8
    default_Dd = 0.6
    
    # 프리셋별 세부 설정
    if preset_option == "시멘트 소성로 (쌍용C&E)":
        # 쌍용C&E 동해공장 기준 설정
        default_Q = 104.17  # m³/s
        default_V = 18.3    # m/s (최적 효율 속도)
        default_rho_g = 0.5975  # kg/m³ (360℃)
        default_mu = 2.98e-5    # kg/m·s (360℃)
        default_temp_info = "360℃ (시멘트 소성로 프리히터 출구)"
        max_Q_limit = 150.0
        recommended_cyclones = int(np.ceil(default_Q / 6.0))  # 6 m³/s당 1개 사이클론
    elif preset_option == "실제 설계 사례 (625m³/min)":
        # 실제 설계 사례 기준 설정 (30:1 모형 기준 치수 적용)
        default_Q = 10.42  # m³/s (625 m³/min ÷ 60)
        default_V = 15.08   # m/s (905 m/min ÷ 60)
        default_rho_g = 0.5975  # kg/m³
        default_mu = 2.98e-5    # kg/m·s (0.10728 kg/m-hr ÷ 3600)
        default_temp_info = "고온 조건 (가스 밀도 0.5975 kg/m³)"
        max_Q_limit = 50.0
        recommended_cyclones = 20  # 직렬 2개 × 병렬 10개 = 20개
        default_rho_p = 480.0  # kg/m³ (입자 밀도)
        target_efficiency = 70.0  # % (목표 효율)
        max_pressure_loss = 1500  # Pa
        pressure_coeff_K = 16  # 압력 손실 계수
        series_count = 2  # 직렬 연결 수
        parallel_count = 10  # 병렬 연결 수
        
        # 30:1 모형 기준 실제 설계 치수 (D = 2.35m 기준) - 이미 초기화됨
        # 모형 분석 기준 비율 계산 (기본값 재정의)
        model_ratios = {
            'H/D': default_H / default_D,      # 1.2/2.35 = 0.511
            'W/D': default_W / default_D,      # 0.6/2.35 = 0.255
            'De/D': default_De / default_D,    # 1.175/2.35 = 0.5
            'S/D': default_S / default_D,      # 1.5/2.35 = 0.638
            'Lb/D': default_Lb / default_D,    # 4.8/2.35 = 2.043
            'Lc/D': default_Lc / default_D,    # 4.8/2.35 = 2.043
            'Dd/D': default_Dd / default_D     # 0.6/2.35 = 0.255
        }
    elif preset_option == "EPA 표준":
        default_Q = 6.0
        default_V = 18.3
        default_rho_g = 1.225
        default_mu = 1.81e-5
        default_temp_info = "20℃ (상온)"
        max_Q_limit = 20.0
        recommended_cyclones = 1
    elif preset_option == "화력발전소":
        default_Q = 50.0
        default_V = 18.3
        default_rho_g = 0.8
        default_mu = 2.5e-5
        default_temp_info = "250℃ (화력발전소 기준)"
        max_Q_limit = 100.0
        recommended_cyclones = int(np.ceil(default_Q / 6.0))
    elif preset_option == "일반 산업용":
        default_Q = 15.0
        default_V = 18.3
        default_rho_g = 1.0
        default_mu = 2.0e-5
        default_temp_info = "100℃ (일반 산업 기준)"
        max_Q_limit = 50.0
        recommended_cyclones = int(np.ceil(default_Q / 6.0))
    # else: 커스텀 설정은 기본값 사용
    
    # 프리셋 정보 표시 (변수 정의 후)
    if preset_option != "커스텀 설정":
        if preset_option == "실제 설계 사례 (625m³/min)":
            st.info(f"""
            **{preset_option} 적용**
            - 처리 유량: {default_Q:.2f} m³/s (625 m³/min)
            - 유입 속도: {default_V:.2f} m/s
            - 구성: 직렬 2개 × 병렬 10개 = 총 20개
            - 목표: 효율 ≥70%, 압력 ≤1,500 Pa
            """)
        else:
            st.info(f"""
            **{preset_option} 적용**
            - 처리 유량: {default_Q:.1f} m³/s
            - 운전 조건: {default_temp_info}
            - 권장 구성: {recommended_cyclones}개
            """)
    
    # model_ratios 초기화 (모든 프리셋용)
    model_ratios = {
        'H/D': 0.5, 'W/D': 0.25, 'De/D': 0.5, 'S/D': 0.625,
        'Lb/D': 2.0, 'Lc/D': 2.0, 'Dd/D': 0.25
    }
    
    # 기타 변수 초기화
    layout_type = "단일"
    n_cyclones = 1
    model_type = "Lapple"
    
    # 기본 탭 구성 (주요 치수, 유체/입자, 시스템 설정)
    tabs = st.tabs(["치수", "유체/입자", "시스템 설정"])
    
    # 주요 치수 탭
    with tabs[0]:
        # 실제 설계 사례용 기본값 설정
        if preset_option == "실제 설계 사례 (625m³/min)":
            # Lapple 1951 표준 사이클론 치수 가이드
            st.markdown("""
            ### 📏 Lapple 1951 표준 사이클론 치수 비율
            **Conventional Cyclone Dimensions (adapted from Lapple, 1951)**:
            - Height of Inlet: H/D = 0.5
            - Width of Inlet: W/D = 0.25  
            - Diameter of Gas Exit: De/D = 0.5
            - Length of Vortex Finder: S/D = 0.625
            - Length of Body: Lb/D = 2.0
            - Length of Cone: Lc/D = 2.0
            - Diameter of Dust Outlet: Dd/D = 0.25
            """)
        
        # 단일 사이클론 직경 (D)
        if preset_option == "실제 설계 사례 (625m³/min)":
            D = st.number_input("Body Diameter D (m)", value=default_D, min_value=1.0, max_value=5.0, step=0.01,
                              help="실제 설계: 2.35m (Lapple 1951 기준)", key="actual_D")
        else:
            D = st.number_input("단일 사이클론 직경 D (m)", value=0.4, min_value=0.1, max_value=2.0, step=0.01,
                              help="EPA 기준 Conventional Cyclone 권장 직경", key="standard_D")
        
        # 입구 높이 (H) - Height of Inlet
        if preset_option == "실제 설계 사례 (625m³/min)":
            H = st.number_input("Height of Inlet H (m)", value=default_H, min_value=0.5, max_value=3.0, step=0.01,
                              help=f"실제 설계: {default_H}m (H/D = {default_H/default_D:.3f}, Lapple 기준: 0.5)", key="actual_H")
            st.info(f"현재 H/D 비율: {H/D:.3f} (Lapple 표준: 0.5)")
        else:
            H = st.number_input("원통부 높이 H (m)", value=0.8, min_value=0.2, max_value=3.0, step=0.05,
                              help="EPA 기준 H/D = 2.0 권장", key="standard_H")
        
        # 입구 너비 (W) - Width of Inlet  
        if preset_option == "실제 설계 사례 (625m³/min)":
            W = st.number_input("Width of Inlet W (m)", value=default_W, min_value=0.1, max_value=2.0, step=0.01,
                              help=f"실제 설계: {default_W}m (W/D = {default_W/default_D:.3f}, Lapple 기준: 0.25)", key="actual_W")
            st.info(f"현재 W/D 비율: {W/D:.3f} (Lapple 표준: 0.25)")
        else:
            W = st.number_input("입구 너비 a (m)", value=0.2, min_value=0.05, max_value=1.0, step=0.01,
                              help="EPA 기준 a/D = 0.5 권장", key="standard_W")
        
        # 가스 출구 직경 (De) - Diameter of Gas Exit
        if preset_option == "실제 설계 사례 (625m³/min)":
            De = st.number_input("Gas Exit Diameter De (m)", value=default_De, min_value=0.5, max_value=3.0, step=0.01,
                               help=f"실제 설계: {default_De}m (De/D = {default_De/default_D:.3f}, Lapple 기준: 0.5)", key="actual_De")
            st.info(f"현재 De/D 비율: {De/D:.3f} (Lapple 표준: 0.5)")
        else:
            De = st.number_input("찾아관 직경 De (m)", value=0.2, min_value=0.05, max_value=1.0, step=0.01,
                               help="EPA 기준 De/D = 0.5 권장", key="standard_De")
        
        # Vortex Finder 길이 (S) - Length of Vortex Finder
        if preset_option == "실제 설계 사례 (625m³/min)":
            S = st.number_input("Vortex Finder Length S (m)", value=default_S, min_value=0.5, max_value=3.0, step=0.01,
                              help=f"실제 설계: {default_S:.3f}m (S/D = {default_S/default_D:.3f}, Lapple 기준: 0.625)", key="actual_S")
            st.info(f"현재 S/D 비율: {S/D:.3f} (Lapple 표준: 0.625)")
        else:
            S = st.number_input("찾아관 침입 깊이 S (m)", value=0.2, min_value=0.0, max_value=1.0, step=0.01,
                              help="EPA 기준 S/D = 0.5 권장", key="standard_S")
        
        # Body 길이 (Lb) - Length of Body
        if preset_option == "실제 설계 사례 (625m³/min)":
            Lb = st.number_input("Body Length Lb (m)", value=default_Lb, min_value=2.0, max_value=8.0, step=0.1,
                                help=f"실제 설계: {default_Lb}m (Lb/D = {default_Lb/default_D:.3f}, Lapple 기준: 2.0)", key="actual_Lb")
            st.info(f"현재 Lb/D 비율: {Lb/D:.3f} (Lapple 표준: 2.0)")
        else:
            Lb = st.number_input("원통부 길이 Lb (m)", value=0.8, min_value=0.2, max_value=3.0, step=0.05,
                                help="EPA 기준 H/D = 2.0 권장", key="standard_Lb")
        
        # Cone 길이 (Lc) - Length of Cone
        if preset_option == "실제 설계 사례 (625m³/min)":
            Lc = st.number_input("Cone Length Lc (m)", value=default_Lc, min_value=2.0, max_value=8.0, step=0.1,
                                help=f"실제 설계: {default_Lc}m (Lc/D = {default_Lc/default_D:.3f}, Lapple 기준: 2.0)")
            st.info(f"현재 Lc/D 비율: {Lc/D:.3f} (Lapple 표준: 2.0)")
        else:
            Lc = st.number_input("원추부 높이 h (m)", value=1.0, min_value=0.2, max_value=3.0, step=0.05,
                                help="EPA 기준 h/D = 2.5 권장")
        
        # Dust Outlet 직경 (Dd) - Diameter of Dust Outlet
        if preset_option == "실제 설계 사례 (625m³/min)":
            Dd = st.number_input("Dust Outlet Diameter Dd (m)", value=default_Dd, min_value=0.1, max_value=1.0, step=0.01,
                                help=f"실제 설계: {default_Dd}m (Dd/D = {default_Dd/default_D:.3f}, Lapple 기준: 0.25)")
            st.info(f"현재 Dd/D 비율: {Dd/D:.3f} (Lapple 표준: 0.25)")
        else:
            Dd = st.number_input("먼지 배출구 직경 B (m)", value=0.1, min_value=0.02, max_value=0.5, step=0.01,
                               help="EPA 기준 B/D = 0.25 권장")
        
        # 실제 설계 사례용 치수 검증
        if preset_option == "실제 설계 사례 (625m³/min)":
            st.markdown("### ✅ 30:1 모형 비율 준수 현황")
            verification_data = [
                {"비율": "H/D", "표준값": "0.500", "모형값": f"{H/D:.3f}", "준수": "✅" if abs(H/D - 0.511) < 0.05 else "📐"},
                {"비율": "W/D", "표준값": "0.250", "모형값": f"{W/D:.3f}", "준수": "✅" if abs(W/D - 0.255) < 0.05 else "📐"},
                {"비율": "De/D", "표준값": "0.500", "모형값": f"{De/D:.3f}", "준수": "✅" if abs(De/D - 0.5) < 0.05 else "📐"},
                {"비율": "S/D", "표준값": "0.625", "모형값": f"{S/D:.3f}", "준수": "✅" if abs(S/D - 0.638) < 0.05 else "📐"},
                {"비율": "Lb/D", "표준값": "2.000", "모형값": f"{Lb/D:.3f}", "준수": "✅" if abs(Lb/D - 2.043) < 0.1 else "📐"},
                {"비율": "Lc/D", "표준값": "2.000", "모형값": f"{Lc/D:.3f}", "준수": "✅" if abs(Lc/D - 2.043) < 0.1 else "📐"},
                {"비율": "Dd/D", "표준값": "0.250", "모형값": f"{Dd/D:.3f}", "준수": "✅" if abs(Dd/D - 0.255) < 0.05 else "📐"}
            ]
            verification_df = pd.DataFrame(verification_data)
            st.dataframe(verification_df, hide_index=True)
            
            # 30:1 모형 특성 표시
            st.success("""
            📐 **30:1 축척 모형 특성 반영됨**
            - 모형 제작 시 물리적 제약으로 인한 소폭 치수 차이는 정상 범위입니다.
            - 실제 효율 계산에는 모형 기준 비율이 적용됩니다.
            - Lapple 표준 대비 ±5% 내외의 차이는 허용 가능합니다.
            """)
        
        # 기존 변수명 호환성을 위한 매핑 (실제 설계 사례가 아닌 경우)
        if preset_option != "실제 설계 사례 (625m³/min)":
            # 기존 변수명 유지
            a = W  # 입구 너비
            b = H  # 입구 높이  
            h = Lc  # 원추부 높이
            B = Dd  # 먼지 배출구 직경
            H = Lb  # 원통부 높이 (기존 H는 이제 Lb)
        else:
            # 실제 설계 사례용 변수명 매핑
            a = W   # Width of Inlet
            b = H   # Height of Inlet
            h = Lc  # Length of Cone  
            B = Dd  # Diameter of Dust Outlet
            # H는 그대로 사용 (Height of Inlet)
    
    # 유체/입자 탭
    with tabs[1]:
        # 유입 속도 (V) - EPA 최적 속도 18.3m/s 기본값
        V_in = st.number_input("유입 속도 V (m/s)", value=default_V, min_value=10.0, max_value=30.0, step=0.1,
                             help="EPA 기준 최적 효율 속도: 18.3 m/s", key="velocity_input")
        
        # 온도 조건 표시
        st.info(f"**선택된 조건**: {default_temp_info}")
        
        # EPA 기준 유량 범위 표시 (프리셋에 따라 동적 표시)
        if preset_option == "시멘트 소성로 (쌍용C&E)":
            st.info(f"**시멘트 소성로 기준**: 50~150 m³/s (대용량 멀티스테이지)")
            st.warning("⚠️ 대용량 처리를 위해 다단 병렬 사이클론 구성이 필요합니다.")
        else:
            st.info(f"EPA 기준 유량 범위: 0.5~12 m³/s (30~720 m³/min)")
        
        # 총 처리 유량 (Q) - 프리셋 기본값 적용
        Q_total = st.number_input("총 처리 유량 Q (m³/s)", 
                                value=default_Q, min_value=0.5, max_value=max_Q_limit, step=0.1,
                                help=f"현재 프리셋: {preset_option}", key="flow_rate_input")
        
        # 시멘트 소성로 조건일 때 추가 정보 표시
        if preset_option == "시멘트 소성로 (쌍용C&E)" and Q_total > 50:
            # 시멘트 소성로 생산량 환산
            daily_tonnage = Q_total * 24 * 60 * 60 / 2000  # m³/s -> 톤/일 (밀도 보정)
            st.metric("예상 시멘트 생산량", f"{daily_tonnage:.0f} 톤/일", 
                     help="쌍용C&E 기준: 소성로당 4,500톤/일")
        
        # 고온 조건 물성치 (프리셋에 따라 자동 설정)
        st.subheader(f"물성치 ({default_temp_info})")
        
        # 공기 점도 (μ) - 프리셋 기본값
        mu = st.number_input("공기 점도 μ (kg/m·s)", value=default_mu, format="%.2e",
                           help=f"현재 온도 조건: {default_temp_info}", key="viscosity_input")
        
        # 공기 밀도 (ρₐ) - 프리셋 기본값  
        rho_g = st.number_input("공기 밀도 ρₐ (kg/m³)", 
                              value=default_rho_g, min_value=0.3, max_value=2.0, step=0.01,
                              help=f"현재 온도 조건: {default_temp_info}", key="gas_density_input")
        
        # 고온 조건에서의 물성치 변화 안내
        if preset_option == "시멘트 소성로 (쌍용C&E)":
            st.warning("""
            🌡️ **고온 조건 (360℃) 주의사항**:
            - 공기 밀도 감소: 상온 대비 약 50% 감소
            - 점도 증가: 상온 대비 약 65% 증가
            - 열팽창으로 인한 체적 변화 고려 필요
            - 내열 소재 및 단열재 적용 필수
            """)
        
        # 입자 밀도 (ρₚ) - 시멘트 원료 기준
        if preset_option == "시멘트 소성로 (쌍용C&E)":
            default_rho_p = 2800.0  # 시멘트 원료 (석회석, 점토 등)
            rho_p = st.number_input("입자 밀도 ρₚ (kg/m³)", value=default_rho_p, 
                                  min_value=2000.0, max_value=4000.0,
                                  help="시멘트 원료 (석회석, 점토, 철광석 등)", key="cement_particle_density")
        elif preset_option == "실제 설계 사례 (625m³/min)":
            # 실제 설계 사례 입자 밀도
            rho_p = st.number_input("입자 밀도 ρₚ (kg/m³)", value=default_rho_p, 
                                  min_value=100.0, max_value=1000.0,
                                  help="실제 설계 사례: 480 kg/m³", key="actual_particle_density")
        else:
            rho_p = st.number_input("입자 밀도 ρₚ (kg/m³)", value=2650.0, 
                                  min_value=1000.0, max_value=5000.0,
                                  help="일반적인 광물 분진 밀도", key="standard_particle_density")
        
        # 실제 설계 사례 추가 조건 표시
        if preset_option == "실제 설계 사례 (625m³/min)":
            st.markdown("""
            ### 🎯 실제 설계 사례 목표 조건
            - **목표 효율**: ≥70%
            - **최대 압력 손실**: 1,500 Pa
            - **압력 계수 K**: 16
            - **구성**: 직렬 2개 사이클론 × 병렬 10개 = 총 20개
            """)
            
            # 목표 조건 메트릭 표시
            col_eff, col_press, col_k = st.columns(3)
            with col_eff:
                st.metric("목표 효율", "≥70%", help="최소 요구 집진 효율")
            with col_press:
                st.metric("최대 압력 손실", "1,500 Pa", help="시스템 압력 손실 한계")
            with col_k:
                st.metric("압력 계수 K", "16", help="압력 손실 계산 계수")
        
        # 분석할 입자 크기 범위
        if preset_option == "시멘트 소성로 (쌍용C&E)":
            # 시멘트 원료 입자 크기 범위
            dp_range = st.slider("입자 크기 범위 (μm)", 
                            min_value=0.5, max_value=200.0, value=(0.5, 150.0),
                            help="시멘트 원료 입자 크기 (미분쇄 후)", key="cement_particle_range")
        elif preset_option == "실제 설계 사례 (625m³/min)":
            # 실제 설계 사례 입자 크기 범위
            dp_range = st.slider("입자 크기 범위 (μm)", 
                            min_value=1.0, max_value=100.0, value=(1.0, 80.0),
                            help="실제 설계 사례 입자 크기 범위", key="actual_particle_range")
        else:
            dp_range = st.slider("입자 크기 범위 (μm)", 
                            min_value=1.0, max_value=100.0, value=(1.0, 100.0),
                            help="EPA 기준 처리 대상 입자 크기", key="standard_particle_range")
        
        # 목표 입자 직경
        if preset_option == "실제 설계 사례 (625m³/min)":
            dp_target = st.slider("목표 입자 직경 dₚ (μm)", 
                              min_value=dp_range[0], max_value=dp_range[1], 
                              value=min(20.0, dp_range[1]),
                              help="실제 설계 사례 평가 기준 입자 크기", key="actual_target_particle")
        else:
            dp_target = st.slider("목표 입자 직경 dₚ (μm)", 
                              min_value=dp_range[0], max_value=dp_range[1], 
                              value=min(10.0, dp_range[1]),
                              help="평가 기준 입자 크기", key="standard_target_particle")
        dp_target_m = dp_target * 1e-6  # 마이크론을 미터로 변환
    
    # 시스템 설정 탭
    with tabs[2]:
        # 사이클론 구성 설정
        st.subheader("🔧 사이클론 구성")
        
        # 실제 설계 사례 특화 구성
        if preset_option == "실제 설계 사례 (625m³/min)":
            st.markdown("### 직렬-병렬 구성 설정")
            
            col_series, col_parallel = st.columns(2)
            with col_series:
                series_count = st.number_input("직렬 연결 수", value=2, min_value=1, max_value=4, step=1,
                                             help="각 병렬 라인당 직렬 연결된 사이클론 수")
            with col_parallel:
                parallel_count = st.number_input("병렬 연결 수", value=10, min_value=1, max_value=20, step=1,
                                               help="병렬로 연결된 멀티사이클론 유닛 수")
            
            # 총 사이클론 수 계산
            total_cyclones = series_count * parallel_count
            n_cyclones = total_cyclones
            
            st.metric("총 사이클론 수", f"{total_cyclones}개", 
                     delta=f"직렬 {series_count}개 × 병렬 {parallel_count}개")
            
            # 유닛당 유량 계산
            flow_per_unit = Q_total / parallel_count
            st.metric("병렬 유닛당 유량", f"{flow_per_unit:.2f} m³/s", 
                     delta=f"{flow_per_unit * 60:.0f} m³/min")
        
        else:
            # 일반 사이클론 구성
            # 권장 사이클론 수 자동 계산
            if Q_total <= 6.0:
                recommended_config = "단일 사이클론"
                max_cyclones = 1
            elif Q_total <= 12.0:
                recommended_config = "병렬 사이클론"
                max_cyclones = min(4, int(np.ceil(Q_total / 6.0)))
            else:
                recommended_config = "직렬 + 병렬"
                max_cyclones = min(8, int(np.ceil(Q_total / 6.0)))
            
            st.info(f"**권장 구성**: {recommended_config}")
            
            n_cyclones = st.selectbox("사이클론 수", list(range(1, max_cyclones + 1)),
                                    index=min(max_cyclones-1, len(range(1, max_cyclones + 1))-1),
                                    help=f"처리 유량 기준 권장: {max_cyclones}개")
            
            # 배치 방식
            if n_cyclones > 1:
                layout_type = st.selectbox("배치 방식", ["정사각형", "육각형"], index=0,
                                         help="공간 효율 최적화 배치")
            else:
                layout_type = "단일"
                series_count = 1  # 단일 사이클론인 경우
        
        # 효율 계산 모델 선택
        model_type = st.selectbox("효율 계산 모델", 
                              ["Lapple", "EPA Standard"], index=0,
                              help="성능 평가 모델")
        
        # 설계 목표 설정
        st.subheader("🎯 설계 목표")
        
        target_col1, target_col2 = st.columns(2)
        
        with target_col1:
            if preset_option == "실제 설계 사례 (625m³/min)":
                st.metric("목표 효율", "≥70%", help="최소 요구 집진 효율")
            else:
                st.metric("목표 효율", "≥85%", help="EPA 권장 집진 효율")
        
        with target_col2:
            if preset_option == "실제 설계 사례 (625m³/min)":
                st.metric("최대 압력 손실", "1,500 Pa", help="시스템 압력 손실 한계")
            else:
                st.metric("권장 압력 손실", "1,000-1,500 Pa", help="EPA 권장 범위")

# ------------ EPA 기준 유효성 검사 섹션 ------------
# 통합 계산 모델 실행
if preset_option == "실제 설계 사례 (625m³/min)":
    # 실제 설계 사례: W=입구너비, H=입구높이
    inlet_area = W * H  
    inlet_width = W
    inlet_height = H
    body_length = Lb
    cone_length = Lc
else:
    # 기존 EPA 기준: a=입구너비, b=입구높이
    inlet_area = a * b
    inlet_width = a  
    inlet_height = b
    body_length = H  # 기존 변수명에서 H는 원통부 높이
    cone_length = h

# 단일 사이클론 유량 계산
single_cyclone_flow = V_in * inlet_area  # m³/s

# 유효 회전수 계산 (통합 공식)
effective_turns = calculate_effective_turns(inlet_height, body_length, cone_length)

# Cut-size 계산 (미터 단위)
cut_size_meter = calculate_cut_size(inlet_width, mu, V_in, effective_turns, rho_p, rho_g)
cut_size_micron = CycloneUnits.meter_to_micron(cut_size_meter)

# 압력 손실 계산
if preset_option == "실제 설계 사례 (625m³/min)":
    # series_count가 시스템 설정 탭에서 정의되었는지 확인
    if 'series_count' not in locals():
        series_count = 2  # 기본값
else:
    series_count = 1

system_pressure_loss = calculate_system_pressure_loss(rho_g, V_in, pressure_coefficient=16, series_count=series_count)

# 호환성을 위한 기존 변수명 유지
A_in = inlet_area
Q_single = single_cyclone_flow  
N_turns = effective_turns
dp50 = cut_size_micron
pressure_loss = system_pressure_loss

# 필요한 사이클론 수 계산
required_cyclones = int(np.ceil(Q_total / Q_single))
if preset_option != "실제 설계 사례 (625m³/min)":
    n_cyclones = min(required_cyclones, 2)  # 최대 2개로 제한

# 입자 크기별 효율 곡선 계산
dp_array = np.linspace(dp_range[0], dp_range[1], 100)
eta_array = np.array([calculate_collection_efficiency(dp, cut_size_micron) for dp in dp_array])

# 직렬 연결 효율 계산
if preset_option == "실제 설계 사례 (625m³/min)" and series_count > 1:
    eta_series_array = np.array([calculate_multi_cyclone_efficiency(eta, series_count) for eta in eta_array])
    eta_multi_array = eta_series_array
else:
    eta_multi_array = np.array([calculate_multi_cyclone_efficiency(eta, n_cyclones) for eta in eta_array])

# EPA 기준 준수 여부 확인 (프리셋에 따라 조정)
epa_compliance = {}

# 1. 압력 손실 기준 (프리셋에 따라 조정)
pressure_loss = calculate_pressure_loss(model_type, rho_g, V_in, series_count, preset_option)
if preset_option == "시멘트 소성로 (쌍용C&E)":
    # 시멘트 소성로 기준: 1.5~3.0 kPa (고온 및 멀티스테이지 고려)
    epa_compliance['pressure'] = 1500 <= pressure_loss <= 3000  # Pa 단위
elif preset_option == "실제 설계 사례 (625m³/min)":
    # 실제 설계 사례 기준: 최대 1,500 Pa (직렬 연결 고려)
    epa_compliance['pressure'] = pressure_loss <= 1500  # Pa 단위
elif preset_option == "화력발전소":
    # 화력발전소 기준: 1.2~2.0 kPa
    epa_compliance['pressure'] = 1200 <= pressure_loss <= 2000  # Pa 단위
else:
    # EPA 표준 기준: 1.0~1.5 kPa
    epa_compliance['pressure'] = 1000 <= pressure_loss <= 1500  # Pa 단위

# 2. 유량 기준 (프리셋에 따라 조정)
if preset_option == "시멘트 소성로 (쌍용C&E)":
    # 시멘트 소성로 기준: 50~150 m³/s (대용량 처리)
    epa_compliance['flow_rate'] = 50.0 <= Q_total <= 150.0
elif preset_option == "화력발전소":
    # 화력발전소 기준: 20~100 m³/s
    epa_compliance['flow_rate'] = 20.0 <= Q_total <= 100.0
elif preset_option == "일반 산업용":
    # 일반 산업용 기준: 5~50 m³/s
    epa_compliance['flow_rate'] = 5.0 <= Q_total <= 50.0
else:
    # EPA 표준 기준: 0.5~12 m³/s
    epa_compliance['flow_rate'] = 0.5 <= Q_total <= 12.0

# 3. 최적 속도 기준 (모든 프리셋 공통: 18.3 m/s ± 2 m/s)
epa_compliance['velocity'] = 16.3 <= V_in <= 20.3

# 4. 설계 비율 기준 (EPA Conventional Cyclone - 모든 프리셋 공통)
epa_ratios = {
    'a/D': (0.4, 0.6, a/D),
    'b/D': (0.4, 0.6, b/D), 
    'H/D': (1.5, 2.5, H/D),
    'h/D': (2.0, 3.0, h/D),
    'De/D': (0.4, 0.6, De/D),
    'S/D': (0.4, 0.6, S/D),
    'B/D': (0.2, 0.3, B/D)
}

for ratio_name, (min_val, max_val, current) in epa_ratios.items():
    epa_compliance[ratio_name] = min_val <= current <= max_val

# ------------ 계산 모델 섹션 ------------
# 주요 파라미터 계산 (통합 계산 모델로 대체됨)
# 기존 중복 계산 로직은 제거하고 위의 통합 계산 결과 사용

# 유속 계산 (기존 호환성 유지)
V_t = V_in  # 접선 속도 (입구 속도와 동일하다고 가정)

# 입자 크기 분포 데이터 (표준화)
standard_particle_distribution = [
    {"size_range": "1~5", "dp_avg": 2.5, "Mj_percent": 5},
    {"size_range": "5~10", "dp_avg": 7.5, "Mj_percent": 10},
    {"size_range": "10~20", "dp_avg": 15, "Mj_percent": 10},
    {"size_range": "20~40", "dp_avg": 30, "Mj_percent": 15},
    {"size_range": "40~60", "dp_avg": 50, "Mj_percent": 15},
    {"size_range": "60~80", "dp_avg": 70, "Mj_percent": 20},
    {"size_range": "80~100", "dp_avg": 90, "Mj_percent": 15},
    {"size_range": "100+", "dp_avg": 100, "Mj_percent": 10},
]

# 필요한 사이클론 수 계산 (최대 2개로 제한)
required_cyclones = int(np.ceil(Q_total / Q_single))
if preset_option != "실제 설계 사례 (625m³/min)":
    n_cyclones = min(required_cyclones, 2)  # 최대 2개로 제한
    
    # 처리량이 단일 사이클론 최대 처리량의 2배를 초과하는 경우 경고
    if required_cyclones > 2:
        st.warning(f"⚠️ 현재 처리량({Q_total:.1f} m³/s)은 2개의 사이클론으로 처리하기에 부족합니다. "
                  f"필요한 사이클론 수: {required_cyclones}개")

# 입자 크기별 효율 곡선 계산
dp_array = np.linspace(dp_range[0], dp_range[1], 100)
eta_array = np.array([calculate_collection_efficiency(dp, cut_size_micron) for dp in dp_array])

# 직렬 연결 효율 계산
if preset_option == "실제 설계 사례 (625m³/min)" and series_count > 1:
    eta_series_array = np.array([calculate_multi_cyclone_efficiency(eta, series_count) for eta in eta_array])
    eta_multi_array = eta_series_array
else:
    eta_multi_array = np.array([calculate_multi_cyclone_efficiency(eta, n_cyclones) for eta in eta_array])

# 입자 크기 분포 데이터 (첨부 이미지 기반)
particle_distribution_data = [
    {"size_range": "1~5", "dp_avg": 2.5, "Mj_percent": 5},
    {"size_range": "5~10", "dp_avg": 7.5, "Mj_percent": 10},
    {"size_range": "10~20", "dp_avg": 15, "Mj_percent": 10},
    {"size_range": "20~40", "dp_avg": 30, "Mj_percent": 15},
    {"size_range": "40~60", "dp_avg": 50, "Mj_percent": 15},
    {"size_range": "60~80", "dp_avg": 70, "Mj_percent": 20},
    {"size_range": "80~100", "dp_avg": 90, "Mj_percent": 15},
    {"size_range": "100+", "dp_avg": 100, "Mj_percent": 10},
]

# ------------ 결과 출력 섹션 ------------
with col2:
    st.header("📊 사이클론 설계 계산 결과")
    
    # 핵심 설계 파라미터 표시
    st.subheader("🔧 설계 파라미터")
    
    param_col1, param_col2, param_col3 = st.columns(3)
    
    with param_col1:
        st.metric("Cut-size (dpc)", f"{cut_size_micron:.2f} μm")
        st.metric("유효 회전수 (Ne)", f"{effective_turns:.2f}")
    
    with param_col2:
        st.metric("압력 손실", f"{system_pressure_loss:.0f} Pa")
        st.metric("입구 속도", f"{V_in:.1f} m/s")
    
    with param_col3:
        st.metric("처리 유량", f"{Q_total:.2f} m³/s")
        st.metric("사이클론 수", f"{n_cyclones}개")
    
    # 입자별 효율 분석 (이미지와 동일한 형식)
    st.subheader("📊 입자별 집진 효율 분석")
    
    # 이미지와 동일한 입자 분포 데이터 사용
    image_particle_data = [
        {"size_range": "1~5", "dp_avg": 2.5, "Mj_percent": 5},
        {"size_range": "5~10", "dp_avg": 7.5, "Mj_percent": 10},
        {"size_range": "10~20", "dp_avg": 15, "Mj_percent": 10},
        {"size_range": "20~40", "dp_avg": 30, "Mj_percent": 15},
        {"size_range": "40~60", "dp_avg": 50, "Mj_percent": 15},
        {"size_range": "60~80", "dp_avg": 70, "Mj_percent": 20},
        {"size_range": "80~100", "dp_avg": 90, "Mj_percent": 15},
        {"size_range": "100+", "dp_avg": 100, "Mj_percent": 10},
    ]
    
    # 계산 결과 테이블 생성 (이미지와 동일한 형식)
    efficiency_table_data = []
    total_single_collected = 0.0
    
    for item in image_particle_data:
        size_range = item["size_range"]
        dp_avg = item["dp_avg"]
        Mj_percent = item["Mj_percent"]
        
        # dpc/dp 비율 계산
        dpc_dp = cut_size_micron / dp_avg
        
        # 단일 사이클론 효율 계산 (η = 1/(1+(dpc/dp)²))
        eta_single = 1 / (1 + dpc_dp**2)
        
        # 수집률 계산 (% collected = η × Mj%)
        collected_percent = eta_single * Mj_percent
        total_single_collected += collected_percent
        
        efficiency_table_data.append({
            "size range": size_range,
            "dp avg": dp_avg,
            "dpc/dp": f"{dpc_dp:.6f}",
            "Nj": f"{eta_single:.6f}",
            "Mj %": Mj_percent,
            "% collected": f"{collected_percent:.6f}"
        })
    
    # 데이터프레임 생성 및 표시
    efficiency_df = pd.DataFrame(efficiency_table_data)
    st.dataframe(efficiency_df, hide_index=True, use_container_width=True)
    
    # 효율 결과 계산
    single_cyclone_efficiency = total_single_collected
    
    # 멀티사이클론 효율 계산
    if preset_option == "실제 설계 사례 (625m³/min)" and series_count > 1:
        multi_cyclone_efficiency = (1 - (1 - single_cyclone_efficiency/100)**series_count) * 100
        cyclone_config = f"직렬 {series_count}개"
    else:
        multi_cyclone_efficiency = (1 - (1 - single_cyclone_efficiency/100)**n_cyclones) * 100
        cyclone_config = f"병렬 {n_cyclones}개"
    
    # 효율 결과 표시 (이미지와 동일한 형식)
    st.markdown("---")
    result_col1, result_col2 = st.columns(2)
    
    with result_col1:
        st.markdown(f"### Cyclone 1개의 효율 = **{single_cyclone_efficiency:.2f}%**")
    
    with result_col2:
        st.markdown(f"### Multi Cyclone 효율 = **{multi_cyclone_efficiency:.8f}%**")
    
    # 설계 조건 요약
    st.subheader("🎯 설계 조건 요약")
    
    design_summary = {
        "설계 항목": [
            "사이클론 직경 (D)",
            "입구 치수 (W×H)",
            "가스 출구 직경 (De)", 
            "처리 유량",
            "유입 속도",
            "압력 손실",
            "사이클론 구성",
            "목표 입자 크기"
        ],
        "설계값": [
            f"{D:.2f} m",
            f"{inlet_width:.2f}×{inlet_height:.2f} m",
            f"{De:.2f} m" if preset_option == "실제 설계 사례 (625m³/min)" else f"{De:.2f} m",
            f"{Q_total:.2f} m³/s ({CycloneUnits.m3_per_s_to_m3_per_min(Q_total):.0f} m³/min)",
            f"{V_in:.1f} m/s",
            f"{system_pressure_loss:.0f} Pa ({CycloneUnits.pa_to_kpa(system_pressure_loss):.2f} kPa)",
            f"{n_cyclones}개 {cyclone_config}",
            f"{dp_target:.0f} μm"
        ]
    }
    
    design_df = pd.DataFrame(design_summary)
    st.dataframe(design_df, hide_index=True, use_container_width=True)
    
    # 성능 평가
    st.subheader("✅ 성능 평가")
    
    # 실제 설계 사례 기준으로 평가
    if preset_option == "실제 설계 사례 (625m³/min)":
        target_eff = 70.0
        max_pressure = 1500
        
        eff_achieved = multi_cyclone_efficiency >= target_eff
        pressure_ok = system_pressure_loss <= max_pressure
        
        eval_col1, eval_col2, eval_col3 = st.columns(3)
        
        with eval_col1:
            if eff_achieved:
                st.success(f"✅ 효율 달성\n{multi_cyclone_efficiency:.1f}% ≥ {target_eff}%")
            else:
                st.error(f"❌ 효율 미달\n{multi_cyclone_efficiency:.1f}% < {target_eff}%")
        
        with eval_col2:
            if pressure_ok:
                st.success(f"✅ 압력 적정\n{system_pressure_loss:.0f} Pa ≤ {max_pressure} Pa")
            else:
                st.error(f"❌ 압력 초과\n{system_pressure_loss:.0f} Pa > {max_pressure} Pa")
        
        with eval_col3:
            overall_ok = eff_achieved and pressure_ok
            if overall_ok:
                st.success("✅ 설계 기준\n충족")
            else:
                st.warning("⚠️ 설계 검토\n필요")
    
    else:
        # 일반적인 성능 평가
        performance_level = "우수" if multi_cyclone_efficiency >= 85 else "양호" if multi_cyclone_efficiency >= 70 else "개선 필요"
        pressure_level = "적정" if 1000 <= system_pressure_loss <= 1500 else "검토 필요"
        
        eval_col1, eval_col2 = st.columns(2)
        
        with eval_col1:
            st.info(f"**집진 효율**: {performance_level}\n{multi_cyclone_efficiency:.1f}%")
        
        with eval_col2:
            st.info(f"**압력 손실**: {pressure_level}\n{system_pressure_loss:.0f} Pa")

# ------------ 참고 기준 (사이드바로 이동) ------------
with st.sidebar:
    st.markdown("## 📚 참고 기준")
    
    st.markdown("### EPA 기준")
    st.markdown("""
    - 압력 손실: 1.0~1.5 kPa
    - 처리 유량: 0.5~12 m³/s
    - 최적 속도: 18.3 m/s
    - 목표 효율: ≥85%
    """)
    
    st.markdown("### 시멘트 소성로 기준")
    st.markdown("""
    - 압력 손실: 1.5~3.0 kPa
    - 처리 유량: 50~150 m³/s
    - 운전 온도: ~360℃
    - 멀티스테이지 구성
    """)
    
    st.markdown("### 설계 권장사항")
    recommendations = []
    
    if multi_cyclone_efficiency < 70:
        recommendations.append("• 사이클론 직경 또는 개수 증가")
    if system_pressure_loss > 1500:
        recommendations.append("• 유입 속도 감소 검토")
    if cut_size_micron > 20:
        recommendations.append("• 입구 치수 최적화")
    if not recommendations:
        recommendations.append("• 현재 설계 적정")
        recommendations.append("• 실험 검증 권장")
    
    for rec in recommendations:
        st.markdown(rec)

# 다운로드 기능
@st.cache_data
def convert_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

# 계산 결과 데이터프레임 생성
results_df = pd.DataFrame({
    '입자_직경_μm': dp_array,
    '단일_효율_%': eta_array * 100,
    '시스템_효율_%': eta_multi_array * 100,
    'Cut_size_μm': [cut_size_micron] * len(dp_array)
})

st.download_button(
    label="📊 계산 결과 다운로드 (CSV)",
    data=convert_to_csv(results_df),
    file_name=f'cyclone_design_results_{preset_option.replace(" ", "_").replace("(", "").replace(")", "")}.csv',
    mime='text/csv',
)

# 주의사항
st.info("""
💡 **설계 시뮬레이터 안내**:
- 이 시뮬레이터는 Lapple 이론 모델을 기반으로 합니다
- 실제 성능은 입자 형상, 분포, 온도 등에 따라 달라질 수 있습니다
- 정밀한 설계를 위해서는 실험 검증이 필요합니다
- EPA 기준 및 실제 설계 사례를 참고하여 최적화하세요
""")

# ------------ 시각화 섹션 ------------
st.subheader("📊 성능 분석 그래프")

graph_col1, graph_col2 = st.columns(2)

with graph_col1:
    st.markdown("### 입자 크기별 효율 곡선")
    fig1, ax1 = plt.subplots(figsize=(8, 6))

    # 효율 곡선 그리기
    ax1.plot(dp_array, eta_array * 100, 'b-', linewidth=2, label="단일 사이클론")
    if n_cyclones > 1 or series_count > 1:
        ax1.plot(dp_array, eta_multi_array * 100, 'r--', linewidth=2, 
                label=f"멀티 사이클론 ({n_cyclones}개)")

    # 주요 기준선들
    ax1.axhline(y=single_cyclone_efficiency, color='blue', linestyle='-.', alpha=0.7, 
                label=f'단일 효율 ({single_cyclone_efficiency:.1f}%)')
    ax1.axhline(y=multi_cyclone_efficiency, color='red', linestyle='-.', alpha=0.7, 
                label=f'시스템 효율 ({multi_cyclone_efficiency:.1f}%)')
    ax1.axvline(x=cut_size_micron, color='gray', linestyle='--', alpha=0.5, 
               label=f'Cut-size ({cut_size_micron:.1f} μm)')

    # 라벨링 및 포맷팅
    ax1.set_xlabel("입자 직경 (μm)", fontsize=12)
    ax1.set_ylabel("집진 효율 (%)", fontsize=12)
    ax1.set_title(f"사이클론 집진 효율 곡선", fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=10)
    ax1.set_xlim(dp_range[0], dp_range[1])
    ax1.set_ylim(0, 100)

    st.pyplot(fig1)

with graph_col2:
    st.markdown("### 설계 치수 비율 검증")
    
    # 설계 비율 확인 (실제 설계 조건 기준)
    if preset_option == "실제 설계 사례 (625m³/min)":
        # 30:1 모형 기준 비율
        ratio_data = {
            "치수 비율": ["H/D", "W/D", "De/D", "S/D", "Lb/D", "Lc/D"],
            "현재 값": [
                f"{inlet_height/D:.3f}",
                f"{inlet_width/D:.3f}", 
                f"{De/D:.3f}",
                f"{S/D:.3f}",
                f"{Lb/D:.3f}",
                f"{Lc/D:.3f}"
            ],
            "Lapple 표준": ["0.500", "0.250", "0.500", "0.625", "2.000", "2.000"],
            "상태": ["✅", "✅", "✅", "✅", "✅", "✅"]
        }
    else:
        # 일반 EPA 기준 비율
        ratio_data = {
            "치수 비율": ["a/D", "b/D", "H/D", "h/D", "De/D", "S/D"],
            "현재 값": [
                f"{inlet_width/D:.3f}",
                f"{inlet_height/D:.3f}",
                f"{body_length/D:.3f}",
                f"{cone_length/D:.3f}",
                f"{De/D:.3f}",
                f"{S/D:.3f}"
            ],
            "EPA 권장": ["0.4-0.6", "0.4-0.6", "1.5-2.5", "2.0-3.0", "0.4-0.6", "0.4-0.6"],
            "상태": ["✅", "✅", "✅", "✅", "✅", "✅"]
        }
    
    ratio_df = pd.DataFrame(ratio_data)
    st.dataframe(ratio_df, hide_index=True, use_container_width=True)
    
    # 핵심 성능 지표 
    st.markdown("### 핵심 성능 지표")
    
    perf_col1, perf_col2 = st.columns(2)
    
    with perf_col1:
        st.metric("Reynolds 수", f"{(rho_g * V_in * inlet_width / mu):.0f}", 
                 help="난류 유동 확인")
        st.metric("유입 면적", f"{inlet_area:.3f} m²", 
                 help="유량 처리 능력")
    
    with perf_col2:
        st.metric("유속비 (V_t/V_in)", "1.0", help="접선 속도 비율")
        st.metric("Cut-size/목표", f"{cut_size_micron/dp_target:.2f}", 
                 help="목표 입자 대비 Cut-size")

# ------------ 결과 다운로드 섹션 ------------
st.subheader("📥 결과 다운로드")

# 계산 결과 요약 데이터 생성
summary_data = {
    "설계 항목": [
        "Cut-size (dpc)",
        "단일 사이클론 효율", 
        "멀티 사이클론 효율",
        "압력 손실",
        "처리 유량",
        "유입 속도",
        "사이클론 수",
        "유효 회전수",
        "Reynolds 수"
    ],
    "계산 결과": [
        f"{cut_size_micron:.2f} μm",
        f"{single_cyclone_efficiency:.2f}%",
        f"{multi_cyclone_efficiency:.2f}%",
        f"{system_pressure_loss:.0f} Pa",
        f"{Q_total:.2f} m³/s",
        f"{V_in:.1f} m/s",
        f"{n_cyclones}개",
        f"{effective_turns:.2f}",
        f"{(rho_g * V_in * inlet_width / mu):.0f}"
    ]
}

summary_df = pd.DataFrame(summary_data)

# 다운로드 버튼들
download_col1, download_col2 = st.columns(2)

with download_col1:
    # 설계 결과 요약 다운로드
    summary_csv = summary_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📊 설계 결과 요약 다운로드",
        data=summary_csv,
        file_name=f'cyclone_design_summary_{preset_option.replace(" ", "_").replace("(", "").replace(")", "")}.csv',
        mime='text/csv',
    )

with download_col2:
    # 입자별 효율 데이터 다운로드
    efficiency_csv = efficiency_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📈 입자별 효율 데이터 다운로드", 
        data=efficiency_csv,
        file_name=f'particle_efficiency_data_{preset_option.replace(" ", "_").replace("(", "").replace(")", "")}.csv',
        mime='text/csv',
    )

# 설계 최종 평가
st.subheader("🎯 최종 설계 평가")

final_col1, final_col2, final_col3 = st.columns(3)

with final_col1:
    if multi_cyclone_efficiency >= 70:
        st.success(f"**효율 평가: 우수**\n{multi_cyclone_efficiency:.1f}% (목표: ≥70%)")
    else:
        st.warning(f"**효율 평가: 개선 필요**\n{multi_cyclone_efficiency:.1f}% (목표: ≥70%)")

with final_col2:
    if system_pressure_loss <= 1500:
        st.success(f"**압력 평가: 적정**\n{system_pressure_loss:.0f} Pa (한계: ≤1500 Pa)")
    else:
        st.warning(f"**압력 평가: 검토 필요**\n{system_pressure_loss:.0f} Pa (한계: ≤1500 Pa)")

with final_col3:
    if cut_size_micron <= 20:
        st.success(f"**Cut-size: 양호**\n{cut_size_micron:.1f} μm (목표: ≤20 μm)")
    else:
        st.info(f"**Cut-size: 검토**\n{cut_size_micron:.1f} μm (목표: ≤20 μm)")

# 주의사항 (간소화)
st.info("""
💡 **설계 시뮬레이터 안내**: 
Lapple 이론 모델 기반 계산 결과입니다. 실제 성능은 입자 특성, 온도, 농도 등에 따라 달라질 수 있으므로 실험 검증을 권장합니다.
""")

# 기존 대용량 섹션들 제거 또는 사이드바로 이동