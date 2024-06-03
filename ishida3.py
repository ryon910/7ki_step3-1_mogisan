import os
import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import set_with_dataframe
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import folium
from streamlit_folium import folium_static

# 環境変数の読み込み
load_dotenv()

# 環境変数から認証情報を取得
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
PRIVATE_KEY_PATH = os.getenv("PRIVATE_KEY_PATH")
SP_SHEET = 'tech0_01'  # sheet名

# セッション状態の初期化
if 'show_all' not in st.session_state:
    st.session_state['show_all'] = False  # 初期状態は地図上の物件のみを表示

# 地図上以外の物件も表示するボタンの状態を切り替える関数
def toggle_show_all():
    st.session_state['show_all'] = not st.session_state['show_all']

# スプレッドシートからデータを読み込む関数
def load_data_from_spreadsheet():
    # googleスプレッドシートの認証 jsonファイル読み込み(key値はGCPから取得)
    SP_CREDENTIAL_FILE = PRIVATE_KEY_PATH
    
    # ファイルの存在を確認
    if not os.path.exists(SP_CREDENTIAL_FILE):
        st.error(f"サービスアカウント認証情報ファイルが見つかりません: {SP_CREDENTIAL_FILE}")
        return None
    
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    try:
        credentials = Credentials.from_service_account_file(SP_CREDENTIAL_FILE, scopes=scopes)
    except Exception as e:
        st.error(f"認証情報の読み込みに失敗しました: {e}")
        return None

    client = gspread.authorize(credentials)
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SP_SHEET)
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    return df

# データフレームの前処理を行う関数
def preprocess_dataframe(df):
    # '家賃' 列を浮動小数点数に変換し、NaN値を取り除く
    df['家賃'] = pd.to_numeric(df['家賃'], errors='coerce')
    df = df.dropna(subset=['家賃'])

    # 最寄り駅情報を統合
    df['最寄り駅'] = df[['アクセス①1駅名', 'アクセス①2駅名', 'アクセス①3駅名']].apply(lambda x: ','.join(x.dropna()), axis=1)
    
    return df

def make_clickable(url, name):
    return f'<a href="{url}" target="_blank">{name}</a>'

def display_search_results(filtered_df):
    # 結果を表示する
    st.write("検索結果", filtered_df.to_html(escape=False, index=False), unsafe_allow_html=True)

def create_map(df):
    # 地図を作成する
    m = folium.Map(location=[df['latitude'].mean(), df['longitude'].mean()], zoom_start=13)
    for idx, row in df.iterrows():
        folium.Marker(
            [row['latitude'], row['longitude']],
            popup=folium.Popup(make_clickable(row['url'], row['物件名']), max_width=300),
            tooltip=row['物件名']
        ).add_to(m)
    return m

def main():
    df = load_data_from_spreadsheet()
    if df is None:
        st.stop()
    
    df = preprocess_dataframe(df)
    
    # 入力フォームの作成
    st.title("不動産検索アプリ")
    st.write("最寄り駅を選択してください")
    
    station_list = sorted(set(df['最寄り駅'].str.split(',').sum()))
    selected_station = st.multiselect('駅名', station_list)
    
    filtered_df = df[df['最寄り駅'].str.split(',').apply(lambda x: any(station in x for station in selected_station))]
    filtered_count = len(filtered_df)
    
    # 'latitude' と 'longitude' 列を数値型に変換し、NaN値を含む行を削除
    filtered_df['latitude'] = pd.to_numeric(filtered_df['latitude'], errors='coerce')
    filtered_df['longitude'] = pd.to_numeric(filtered_df['longitude'], errors='coerce')
    filtered_df2 = filtered_df.dropna(subset=['latitude', 'longitude'])
    
    # 検索ボタン / フィルタリングされたデータフレームの件数を表示
    col2_1, col2_2 = st.columns([1, 2])
    
    with col2_2:
        st.write(f"物件検索数: {filtered_count}件 / 全{len(df)}件")
    
    # 検索ボタン
    if col2_1.button('検索＆更新', key='search_button'):
        # 検索ボタンが押された場合、セッションステートに結果を保存
        st.session_state['filtered_df'] = filtered_df
        st.session_state['filtered_df2'] = filtered_df2
        st.session_state['search_clicked'] = True
    
    # Streamlitに地図を表示
    if st.session_state.get('search_clicked', False):
        m = create_map(st.session_state.get('filtered_df2', filtered_df2))
        folium_static(m)
    
    # 地図の下にラジオボタンを配置し、選択したオプションに応じて表示を切り替える
    show_all_option = st.radio(
        "表示オプションを選択してください:",
        ('地図上の検索物件のみ', 'すべての検索物件'),
        index=0 if not st.session_state.get('show_all', False) else 1,
        key='show_all_option'
    )
    
    # ラジオボタンの選択に応じてセッションステートを更新
    st.session_state['show_all'] = (show_all_option == 'すべての検索物件')
    
    # 検索結果の表示
    if st.session_state.get('search_clicked', False):
        if st.session_state['show_all']:
            display_search_results(st.session_state.get('filtered_df', filtered_df))  # 全データ
        else:
            display_search_results(st.session_state.get('filtered_df2', filtered_df2))  # 地図上の物件のみ

# アプリケーションの実行
if __name__ == "__main__":
    if 'search_clicked' not in st.session_state:
        st.session_state['search_clicked'] = False
    if 'show_all' not in st.session_state:
        st.session_state['show_all'] = False
    main()
