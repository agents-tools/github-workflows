class WorkflowHello < Formula
  desc "Print a greeting"
  homepage "https://www.gnu.org/software/hello/"
  url "https://ftpmirror.gnu.org/gnu/hello/hello-2.12.2.tar.gz"
  sha256 "5a9a996dc292cc24dcf411cee87e92f6aae5b8d13bd9c6819b4c7a9dce0818ab"
  license "GPL-3.0-or-later"

  def install
    system "./configure", "--disable-nls", *std_configure_args
    system "make", "install"
  end

  test do
    assert_equal "Hello, world!\n", shell_output("#{bin}/hello")
  end
end
