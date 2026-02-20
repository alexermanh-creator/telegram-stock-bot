
import matplotlib.pyplot as plt
from portfolio import get_portfolio

def create_allocation_chart(path="allocation.png"):
    data = get_portfolio()
    labels = ["Crypto","Stock"]
    sizes = [data["crypto"]["value"], data["stock"]["value"]]
    plt.figure()
    plt.pie(sizes, labels=labels, autopct='%1.1f%%')
    plt.savefig(path)
    plt.close()
    return path
