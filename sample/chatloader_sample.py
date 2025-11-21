from chat_downloader import ChatDownloader
from matplotlib import pyplot
import matplotlib.pyplot as plt


class FunctionUtils:

    # ネストデータにアクセスする関数
    @staticmethod
    def nested_item_value(parrent_object, nest_list):
        """ return nested data """

        if not nest_list: return parrent_object

        result = ""
        for nest_key in nest_list:
            object_type = type(parrent_object)
            if object_type is not dict and object_type is not list:
                result = None
                break
            elif object_type is list:
                if type(nest_key) is not int:
                    result = None
                    break
                result = parrent_object[nest_key] if nest_key < len(parrent_object) else None
            else:
                result = parrent_object.get(nest_key, None)

            if result is None:
                break

            parrent_object = result

        return result


def chat_count(lists):
    lists_count = []
    i = 0

    while i <= (max(lists)):
        if i in lists:
            lists_count.append(lists.count(i))
        else:
            lists_count.append(0)
        i += 1

    return lists_count


def main():
    fu = FunctionUtils()
    chat_time = []
    chat_member = []
    chat_mess = []

    def motion(event):
        x = event.xdata
        y = event.ydata
        try:
            ln_v.set_xdata(round(x))
        except TypeError:
            pass

        plt.draw()

    def onclick(event):
        print('event.xdata={}'.format(round(event.xdata)))
        print('message_count={}'.format(message_count[round(event.xdata)]))

    # URLからchatを読み込み
    # --------------------------------------------------------------------
    url = 'ここにYoutubeのURLを書き込む'
    start = 'ここに読み込みを開始する秒数を書き込む（0:00）'
    end = 'ここに読み込みを終了する秒数を書き込む（0:10）'
    chat = ChatDownloader().get_chat(url,
                                     start_time=start,
                                     end_time=end
                                     )

    # --------------------------------------------------------------------

    for message in chat:  # iterate over messages
        time_in_seconds = round(fu.nested_item_value(message, ["time_in_seconds"]))
        chat_mess.append(fu.nested_item_value(message, ["message"]))
        chat_time.append(time_in_seconds)

        if (fu.nested_item_value(message, ["author", "badges", 0, "title"])) is not None:
            chat_member.append(time_in_seconds)

    message_count = chat_count(chat_time)  # chat_count メソッドを呼び出す
    member_count = chat_count(chat_member)

    fig = plt.figure()

    c1, c2, c3, c4 = "blue", "green", "red", "black"

    pyplot.plot(member_count, "o-", picker=1, color=c3)
    pyplot.plot(message_count, "o-", picker=1, color=c1)

    ln_v = plt.axvline(0)

    plt.connect('motion_notify_event', motion)
    fig.canvas.mpl_connect('button_press_event', onclick)

    pyplot.show()


if __name__ == '__main__':
    main()

