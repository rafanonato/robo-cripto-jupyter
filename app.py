import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm
import math
import pickle
import time
from flask import Flask, jsonify, request
import math
from sqlalchemy import create_engine

app = Flask(__name__)

# Carregando modelo criado
# model = pickle.load(open('nosso_modelo.pickle', 'rb'))
token = '7815696ecbf1c96e6894b779456d330e'
ticker = 'BTCUSDT'
valor_compra_venda = 10

urlbase = 'https://mighty-bastion-45199.herokuapp.com/'


def get_result(x):
    try:
        result = pd.DataFrame.from_dict(x.json())
    except:
        result = x.text
    return result


def api_post(route, payload):
    url = urlbase + route
    x = requests.post(url, data=payload)
    df = get_result(x)
    if type(df) == pd.core.frame.DataFrame:
        if 'datetime' in df.columns:
            df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
    return df


def api_get(route):
    url = urlbase + route
    x = requests.get(url)
    df = get_result(x)
    return df


def tratamento(data):
    data['cont'] = range(0, data.shape[0])
    data.rename(columns={'close': 'valor'}, inplace=True)
    data.loc[:, 'target_num'] = data['valor'].shift(-1)
    data.loc[:, 'target'] = data['target_num'] - data['valor']
    data = data.drop(columns=['target_num'])
    data = data[data["target"] != "NaN"]
    data['target'].unique()
    data.dropna(axis=0, how='all')
    nan_value = float("NaN")
    data.replace("", nan_value, inplace=True)
    data.dropna(subset=["target"], inplace=True)
    data_1 = data[['valor', 'volume', 'cont', 'target', 'datetime']].reset_index(drop=True)
    data_1['Data'] = data_1['datetime'].dt.strftime('%Y-%m-%d')
    # Coluna 'Hora'
    data_1['Hora'] = data_1['datetime'].dt.strftime('%H:%M:%S')
    data_1['Data'] = pd.to_datetime(data_1['Data'])  ## Alterar o tipo para data
    data_1['Dia_da_Semana'] = data_1['Data'].dt.day_name()
    conditions = [
        (data_1["Dia_da_Semana"] == "Sunday"),
        (data_1["Dia_da_Semana"] == "Monday"),
        (data_1["Dia_da_Semana"] == "Tuesday"),
        (data_1["Dia_da_Semana"] == "Wednesday"),
        (data_1["Dia_da_Semana"] == "Thursday"),
        (data_1["Dia_da_Semana"] == "Friday"),
        (data_1["Dia_da_Semana"] == "Saturday")]
    choices = [1, 2, 3, 4, 5, 6, 7]
    data_1['Dia_da_semana'] = np.select(conditions, choices, default=0)
    data_1 = data_1.sort_values(['datetime'])
    data_1['valor_ma_5'] = data_1['valor'].rolling(window=5).mean()
    data_1['preco_lag60m'] = data_1['valor'].shift(60)
    data_1['diff_5'] = data_1['valor'].diff(periods=5)
    data_1['dia'] = data_1['Data'].dt.day
    data_1['mês'] = data_1['Data'].dt.month
    data_1['ano'] = data_1['Data'].dt.year
    conditions = [
        (data_1['dia'] / 7 <= 1),
        ((data_1['dia'] / 7 > 1) & (data_1['dia'] / 7 <= 2)),
        ((data_1['dia'] / 7 > 2) & (data_1['dia'] / 7 <= 3)),
        ((data_1['dia'] / 7 > 3) & (data_1['dia'] / 7 <= 4)),
        (data_1['dia'] / 7 > 4)]
    choices = [1, 2, 3, 4, 5]
    data_1['Semana_Mês'] = np.select(conditions, choices, default=0)
    # Criação de variável tendencias
    data_1['tend_med_60m'] = data_1['valor'].rolling(window=60).mean()
    data_1['tend_med_5m'] = data_1['valor'].rolling(window=5).mean()
    data_1['tend_ult_5m/60m'] = data_1['tend_med_5m'] / data_1['tend_med_60m']

    data_1['tend_med_720m'] = data_1['valor'].rolling(window=480).mean()
    data_1['tend_ult_60m/720m'] = data_1['tend_med_60m'] / data_1['tend_med_720m']
    data_1['tend_max_60m'] = data_1['valor'].rolling(window=60).max()
    data_1['tend_min_60m'] = data_1['valor'].rolling(window=60).min()
    data_1['tend60_max/min'] = data_1['tend_max_60m'] / data_1['tend_min_60m']
    data_1 = data_1[
        ['valor', 'volume', 'cont', 'target', 'Data', 'Dia_da_semana', 'preco_lag60m', 'diff_5', 'Semana_Mês',
         'tend_med_60m', 'tend_med_5m', 'tend_ult_5m/60m', 'tend_med_720m', 'tend_ult_60m/720m', 'tend_max_60m',
         'tend_min_60m', 'tend60_max/min']].reset_index(drop=True)
    df = data_1
    df = df.dropna()
    df.head()
    return df


def compute_quantity(coin_value, invest_value, significant_digits):
    a_number = invest_value / coin_value
    rounded_number = round(a_number, significant_digits - int(math.floor(math.log10(abs(a_number)))) - 1)
    print(rounded_number)
    return rounded_number  # .iloc[0]


def how_much_i_have(ticker, token):
    status = api_post('status', payload={'token': token})
    status_this_coin = status.query(f"ticker == '{ticker}'")
    if status_this_coin.shape[0] > 0:
        return status_this_coin['quantity'].iloc[0]
    else:
        return 0


def my_robot(tempo, token):
    # model = pickle.load(open('nosso_modelo.pickle', 'rb'))
    #  model = pickle.load(open('nosso_modelo.pkl', 'rb'))
    ticker = 'BTCUSDT'
    count_iter = 0
    valor_compra_venda = 10

    while count_iter < tempo:

        # Pegando o OHLC dos últimos 500 minutos
        df = api_post('cripto_quotation', {'token': token, 'ticker': ticker})

        # Realizando a engenharia de features
        df = tratamento(df)
        print(df)

        # Isolando a linha mais recente
        df_last = df.iloc[-1]
        print(df_last)
        # df_last = df.iloc[[np.argmax(df['time'])]]

        # Calculando tendência, baseada no modelo linear criado
        # tendencia = model.predict(df_last).iloc[0]
        tendencia = 1

        # A quantidade de cripto que será comprada/ vendida depende do valor_compra_venda e da cotação atual
        qtdade = compute_quantity(coin_value=df_last['valor'], invest_value=valor_compra_venda, significant_digits=2)

        # Print do datetime atual
        print('-------------------')
        print(f"@{pd.to_datetime('now')}")

        if tendencia > 0.02:
            # Modelo detectou uma tendência positiva
            print(f"Tendência positiva de {str(tendencia)}")

            # Verifica quanto dinheiro tem em caixa
            qtdade_money = how_much_i_have('money', token)

            if qtdade_money > 0:
                # Se tem dinheiro, tenta comprar o equivalente a qtdade ou o máximo que o dinheiro permitir
                max_qtdade = compute_quantity(coin_value=df_last['valor'], invest_value=qtdade_money,
                                              significant_digits=2)
                qtdade = min(qtdade, max_qtdade)

                # Realizando a compra
                print(f'Comprando {str(qtdade)} {ticker}')
                api_post('buy', payload={'token': token, 'ticker': ticker, 'quantity': qtdade})

        elif tendencia < -0.02:
            # Modelo detectou uma tendência negativa
            print(f"Tendência negativa de {str(tendencia)}")

            # Verifica quanto tem da moeda em caixa
            qtdade_coin = how_much_i_have(ticker, token)

            if qtdade_coin > 0:
                # Se tenho a moeda, vou vender!
                qtdade = min(qtdade_coin, qtdade)
                print(f'Vendendo {str(qtdade)} {ticker}')
                api_post('sell', payload={'token': token, 'ticker': ticker, 'quantity': qtdade})
        else:
            # Não faz nenhuma ação, espera próximo loop
            print(f"Tendência neutra de {str(tendencia)}. Nenhuma ação realizada")

        # Print do status após cada iteração
        print(api_post('status', payload={'token': token}))
        count_iter += 1
        time.sleep(60)


token = '7815696ecbf1c96e6894b779456d330e'


@app.route("/")
def index():
    return "Robo Cripto"


@app.route('/wakeup', methods=["POST"])
def wakeup():
    """
    Exemplo de Utilização:

    import requests
    url = 'http://127.0.0.1:5000/wakeup'
    try:
        x = requests.post(, data = {'time': 10}, timeout=6)
    except requests.exceptions.ReadTimeout:
        pass
    """
    tempo = int(request.form.get("time"))
    if not tempo:
        return "Group token must be provided", None

    # my_robot é a função com o loop que realiza as compras/ vendas (conforme notebook 2_my_robot.ipynb)
    my_robot(tempo, token)


app.run()


